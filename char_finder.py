#!/usr/bin/env python3
"""
char_finder.py — Anime character finder
Learns a character from a small reference dataset, scans a large image folder,
moves matched images to output (no copy).

Usage:
  python char_finder.py train  --ref ./ref_images  --model ./char_model.pth
  python char_finder.py scan   --model ./char_model.pth --source ./15k_images --output ./found --threshold 0.75
  python char_finder.py run    --ref ./ref_images  --source ./15k_images --output ./found
"""

import argparse
import os
import sys
import shutil
import random
import time
import json
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
from PIL import Image, ImageFilter, ImageEnhance
from tqdm import tqdm

# ── Constants ─────────────────────────────────────────────────────────────────

IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
IMG_SIZE = 224
BATCH_SIZE = 32
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ── Augmentation tailored for anime art ───────────────────────────────────────

def anime_train_transform():
    """
    Anime-specific augmentation:
    - Conservative hue/sat shift (anime palettes are intentional)
    - Mild blur to simulate different art styles
    - No aggressive color jitter that destroys line art
    """
    return transforms.Compose([
        transforms.Resize((IMG_SIZE + 32, IMG_SIZE + 32)),
        transforms.RandomCrop(IMG_SIZE),
        transforms.RandomHorizontalFlip(),
        transforms.RandomApply([transforms.GaussianBlur(3, sigma=(0.1, 1.0))], p=0.2),
        transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2, hue=0.05),
        transforms.RandomGrayscale(p=0.05),
        transforms.ToTensor(),
        transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
    ])

def val_transform():
    return transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
    ])

# ── Dataset ────────────────────────────────────────────────────────────────────

class CharDataset(Dataset):
    def __init__(self, samples, transform):
        # samples: list of (path, label) where label 1=char, 0=negative
        self.samples = samples
        self.transform = transform

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        try:
            img = Image.open(path).convert("RGB")
            img = self.transform(img)
        except Exception:
            img = torch.zeros(3, IMG_SIZE, IMG_SIZE)
        return img, torch.tensor(label, dtype=torch.float32)


class InferenceDataset(Dataset):
    def __init__(self, paths, transform):
        self.paths = paths
        self.transform = transform

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        path = self.paths[idx]
        try:
            img = Image.open(path).convert("RGB")
            img = self.transform(img)
            ok = True
        except Exception:
            img = torch.zeros(3, IMG_SIZE, IMG_SIZE)
            ok = False
        return img, str(path), ok

# ── Model ──────────────────────────────────────────────────────────────────────

def build_model():
    """EfficientNet-B0 with custom binary head."""
    model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)
    in_features = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(0.3),
        nn.Linear(in_features, 128),
        nn.ReLU(),
        nn.Dropout(0.2),
        nn.Linear(128, 1),
    )
    return model.to(DEVICE)

# ── Negative sample generation ─────────────────────────────────────────────────

def collect_negatives(source_dir: Path, ref_paths: set, count: int) -> list:
    """
    Collect negative samples from source_dir, excluding ref images.
    Picks randomly to avoid bias toward any single visual pattern.
    """
    all_imgs = [
        p for p in source_dir.rglob("*")
        if p.suffix.lower() in IMG_EXTENSIONS and str(p) not in ref_paths
    ]
    random.shuffle(all_imgs)
    return all_imgs[:count]

# ── Training ───────────────────────────────────────────────────────────────────

def train(ref_dir: Path, source_dir: Path, model_path: Path, epochs: int = 15):
    print(f"\n[DEVICE] {DEVICE}")
    print(f"[REF]    {ref_dir}")

    # Collect positives
    positives = [
        p for p in ref_dir.rglob("*")
        if p.suffix.lower() in IMG_EXTENSIONS
    ]
    if len(positives) < 3:
        print(f"[ERROR] Need at least 3 reference images, found {len(positives)}")
        sys.exit(1)
    print(f"[INFO]  Positive samples : {len(positives)}")

    # Negative samples = 3× positives for balance
    neg_count = len(positives) * 3
    ref_set = {str(p) for p in positives}

    if source_dir and source_dir.exists():
        negatives = collect_negatives(source_dir, ref_set, neg_count)
    else:
        # Fallback: no source provided, train with only positives + synthetic
        negatives = []
    print(f"[INFO]  Negative samples : {len(negatives)}")

    if len(negatives) == 0:
        print("[WARN]  No negative samples found. Training only on positives (less reliable).")
        print("        Provide --source path to get better results.")

    samples = [(p, 1) for p in positives] + [(p, 0) for p in negatives]
    random.shuffle(samples)

    # Split 85/15 train/val
    split = max(1, int(len(samples) * 0.85))
    train_data = CharDataset(samples[:split], anime_train_transform())
    val_data   = CharDataset(samples[split:], val_transform()) if split < len(samples) else None

    train_loader = DataLoader(train_data, batch_size=min(BATCH_SIZE, len(train_data)),
                              shuffle=True, num_workers=2, pin_memory=True)

    model = build_model()
    criterion = nn.BCEWithLogitsLoss()

    # Two-phase: freeze backbone first, then unfreeze for fine-tuning
    for param in model.features.parameters():
        param.requires_grad = False

    optimizer = optim.Adam(model.classifier.parameters(), lr=1e-3)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_loss = float("inf")
    best_state = None

    print(f"\n[TRAIN] Phase 1: Classifier head only (epochs 1-{max(1, epochs//3)})")
    phase1_epochs = max(1, epochs // 3)

    for epoch in range(1, epochs + 1):
        # Unfreeze backbone after phase 1
        if epoch == phase1_epochs + 1:
            print(f"[TRAIN] Phase 2: Full fine-tune (epoch {epoch}+)")
            for param in model.features.parameters():
                param.requires_grad = True
            optimizer = optim.Adam(model.parameters(), lr=5e-5, weight_decay=1e-4)
            scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs - phase1_epochs)

        model.train()
        total_loss = 0.0
        correct = 0

        for imgs, labels in train_loader:
            imgs, labels = imgs.to(DEVICE), labels.to(DEVICE)
            optimizer.zero_grad()
            logits = model(imgs).squeeze(1)
            loss = criterion(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += loss.item()
            preds = (torch.sigmoid(logits) > 0.5).float()
            correct += (preds == labels).sum().item()

        scheduler.step()
        acc = correct / len(train_data) * 100

        val_info = ""
        if val_data and len(val_data) > 0:
            model.eval()
            val_loader = DataLoader(val_data, batch_size=BATCH_SIZE, num_workers=2)
            val_loss = 0.0
            with torch.no_grad():
                for imgs, labels in val_loader:
                    imgs, labels = imgs.to(DEVICE), labels.to(DEVICE)
                    logits = model(imgs).squeeze(1)
                    val_loss += criterion(logits, labels).item()
            val_info = f"  val_loss={val_loss/len(val_loader):.4f}"
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        print(f"  Epoch {epoch:3d}/{epochs}  loss={total_loss/len(train_loader):.4f}  acc={acc:.1f}%{val_info}")

    # Save best or last
    save_state = best_state if best_state else model.state_dict()
    meta = {
        "positives": len(positives),
        "negatives": len(negatives),
        "epochs": epochs,
        "img_size": IMG_SIZE,
    }
    torch.save({"state_dict": save_state, "meta": meta}, model_path)
    print(f"\n[SAVED] Model → {model_path}")
    print(f"[META]  {meta}")

# ── Scanning ───────────────────────────────────────────────────────────────────

def scan(model_path: Path, source_dir: Path, output_dir: Path,
         threshold: float = 0.75, dry_run: bool = False):

    if not model_path.exists():
        print(f"[ERROR] Model not found: {model_path}")
        sys.exit(1)

    print(f"\n[DEVICE]    {DEVICE}")
    print(f"[MODEL]     {model_path}")
    print(f"[SOURCE]    {source_dir}")
    print(f"[OUTPUT]    {output_dir}")
    print(f"[THRESHOLD] {threshold}")

    checkpoint = torch.load(model_path, map_location=DEVICE)
    model = build_model()
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    print(f"[META]  {checkpoint.get('meta', {})}")

    # Collect all images
    all_imgs = sorted([
        p for p in source_dir.rglob("*")
        if p.suffix.lower() in IMG_EXTENSIONS
    ])
    print(f"[INFO]  Found {len(all_imgs):,} images to scan\n")

    dataset = InferenceDataset(all_imgs, val_transform())
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, num_workers=4,
                        pin_memory=True, prefetch_factor=2)

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    matched = 0
    errors = 0
    log_entries = []

    start = time.time()

    with torch.no_grad():
        for imgs, paths, oks in tqdm(loader, desc="Scanning", unit="batch"):
            imgs = imgs.to(DEVICE)
            logits = model(imgs).squeeze(1)
            scores = torch.sigmoid(logits).cpu().tolist()

            for path, score, ok in zip(paths, scores, oks):
                path = Path(path)
                if not ok:
                    errors += 1
                    continue
                if score >= threshold:
                    matched += 1
                    log_entries.append({"file": path.name, "score": round(score, 4)})
                    if not dry_run:
                        dest = output_dir / path.name
                        # Handle name collision
                        if dest.exists():
                            stem = path.stem
                            suffix = path.suffix
                            i = 1
                            while dest.exists():
                                dest = output_dir / f"{stem}_{i}{suffix}"
                                i += 1
                        shutil.move(str(path), str(dest))

    elapsed = time.time() - start
    rate = len(all_imgs) / elapsed if elapsed > 0 else 0

    print(f"\n{'─'*50}")
    print(f"  Scanned  : {len(all_imgs):,} images")
    print(f"  Matched  : {matched:,} images  (threshold={threshold})")
    print(f"  Errors   : {errors}")
    print(f"  Time     : {elapsed:.1f}s  ({rate:.0f} img/s)")
    if not dry_run:
        print(f"  Output   : {output_dir}")
    print(f"{'─'*50}\n")

    # Write log
    if not dry_run and log_entries:
        log_path = output_dir / "_scan_log.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump({
                "threshold": threshold,
                "matched": matched,
                "total_scanned": len(all_imgs),
                "results": sorted(log_entries, key=lambda x: x["score"], reverse=True)
            }, f, indent=2, ensure_ascii=False)
        print(f"[LOG]  {log_path}")

# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Anime character finder — learn from small dataset, scan large folder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # ── train ──
    p_train = sub.add_parser("train", help="Fine-tune model on reference images")
    p_train.add_argument("--ref",    required=True, type=Path, help="Folder of reference images (positive)")
    p_train.add_argument("--source", type=Path, default=None,  help="Large image folder for negatives (recommended)")
    p_train.add_argument("--model",  required=True, type=Path, help="Output model path (.pth)")
    p_train.add_argument("--epochs", type=int, default=15,     help="Training epochs (default: 15)")

    # ── scan ──
    p_scan = sub.add_parser("scan", help="Scan large folder and move matched images")
    p_scan.add_argument("--model",     required=True, type=Path,  help="Trained model (.pth)")
    p_scan.add_argument("--source",    required=True, type=Path,  help="Large image folder to scan")
    p_scan.add_argument("--output",    required=True, type=Path,  help="Output folder for matched images")
    p_scan.add_argument("--threshold", type=float, default=0.75,  help="Confidence threshold 0-1 (default: 0.75)")
    p_scan.add_argument("--dry-run",   action="store_true",       help="Preview matches without moving")

    # ── run (train + scan in one go) ──
    p_run = sub.add_parser("run", help="Train then immediately scan (all-in-one)")
    p_run.add_argument("--ref",       required=True, type=Path)
    p_run.add_argument("--source",    required=True, type=Path)
    p_run.add_argument("--output",    required=True, type=Path)
    p_run.add_argument("--model",     type=Path, default=Path("char_model.pth"))
    p_run.add_argument("--epochs",    type=int, default=15)
    p_run.add_argument("--threshold", type=float, default=0.75)
    p_run.add_argument("--dry-run",   action="store_true")

    args = parser.parse_args()

    if args.cmd == "train":
        train(args.ref, args.source, args.model, args.epochs)

    elif args.cmd == "scan":
        scan(args.model, args.source, args.output, args.threshold, args.dry_run)

    elif args.cmd == "run":
        train(args.ref, args.source, args.model, args.epochs)
        scan(args.model, args.source, args.output, args.threshold, args.dry_run)

if __name__ == "__main__":
    main()
