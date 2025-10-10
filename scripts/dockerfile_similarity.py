import os
import difflib
import itertools
import pandas as pd

# --- Color helpers for terminal output ---
def green(text): return f"\033[92m{text}\033[0m"
def red(text): return f"\033[91m{text}\033[0m"

def colorize_terminal(value):
    """Return a green-colored string for values >=70% and <100%."""
    if 70 <= value < 100:
        return green(f"{value:.1f}%")
    else:
        return f"{value:.1f}%"

# --- Helper for CSV output highlighting ---
def mark_high_values(value):
    """Mark high similarity values (>85% and <100%) with a ✅ for CSV output."""
    if 85 < value < 100:
        return f"{value:.1f}% ✅"
    else:
        return f"{value:.1f}%"

def read_dockerfile(path):
    """Read a Dockerfile and clean comments and empty lines."""
    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines()
                 if line.strip() and not line.strip().startswith('#')]
    return lines

def dockerfile_similarity(lines1, lines2):
    """Compute similarity ratio between two Dockerfiles."""
    text1 = "\n".join(lines1)
    text2 = "\n".join(lines2)
    return difflib.SequenceMatcher(None, text1, text2).ratio()

def common_blocks(lines1, lines2, min_block_size=2):
    """Find contiguous common code blocks between two Dockerfiles."""
    matcher = difflib.SequenceMatcher(None, lines1, lines2)
    blocks = []
    for match in matcher.get_matching_blocks():
        if match.size >= min_block_size:
            block = lines1[match.a:match.a + match.size]
            blocks.append(block)
    return blocks

def show_diff(lines1, lines2, name1, name2):
    """Print unified diff between two Dockerfiles, color-coded."""
    diff = difflib.unified_diff(
        lines1, lines2,
        fromfile=name1,
        tofile=name2,
        lineterm=''
    )
    for line in diff:
        if line.startswith('+') and not line.startswith('+++'):
            print(red(line))
        elif line.startswith('-') and not line.startswith('---'):
            print(red(line))
        elif line.startswith('@@'):
            print(f"\033[95m{line}\033[0m")  # purple diff range
        else:
            print(line)

def compare_dockerfiles(dockerfiles):
    """Compare all Dockerfiles pairwise."""
    contents = {f: read_dockerfile(f) for f in dockerfiles}
    pairs = list(itertools.combinations(dockerfiles, 2))
    
    data = []
    common_data = {}

    for f1, f2 in pairs:
        sim = dockerfile_similarity(contents[f1], contents[f2])
        sim_percent = sim * 100  # convert to percentage
        data.append((os.path.basename(f1), os.path.basename(f2), sim_percent))
        common_data[(f1, f2)] = common_blocks(contents[f1], contents[f2])

    # Build similarity matrix
    names = [os.path.basename(f) for f in dockerfiles]
    df = pd.DataFrame(0.0, index=names, columns=names)
    for f1, f2, sim in data:
        df.at[f1, f2] = sim
        df.at[f2, f1] = sim
    for name in names:
        df.at[name, name] = 100.0

    return df, common_data, contents


if __name__ == "__main__":
    # --- Auto-detect correct folder path ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    folder = os.path.join(script_dir, "dockerfiles")
    folder = os.path.normpath(folder)

    dockerfiles = [
        "Dockerfile.datascience.cpu",
        "Dockerfile.minimal.cpu",
        "Dockerfile.minimal.cuda",
        "Dockerfile.minimal.rocm",
        "Dockerfile.pytorch.cuda",
        "Dockerfile.pytorch.rocm",
        "Dockerfile.pytorchllmcompressor.cuda",
        "Dockerfile.tensorflow.cuda",
        "Dockerfile.tensorflow.rocm",
        "Dockerfile.trustyai.cpu",
    ]

    dockerfiles = [os.path.join(folder, f) for f in dockerfiles]

    # --- Sanity check for missing files ---
    missing = [f for f in dockerfiles if not os.path.exists(f)]
    if missing:
        print("❌ Missing Dockerfiles:")
        for f in missing:
            print("   ", f)
        raise FileNotFoundError("Some Dockerfiles are missing. Please check names/locations.")
    else:
        print(f"✅ Found {len(dockerfiles)} Dockerfiles in {folder}")

    # --- Run comparison ---
    df, common, contents = compare_dockerfiles(dockerfiles)
    
    print("\n=== 📊 Dockerfile Similarity Matrix (Percentages) ===")

    # Pretty print with colors in terminal
    header = ["".ljust(30)] + [name.ljust(30) for name in df.columns]
    print(" ".join(header))
    for idx, row in df.iterrows():
        row_str = [idx.ljust(30)] + [colorize_terminal(val).ljust(30) for val in row]
        print(" ".join(row_str))

    # --- Save CSV with highlights ---
    df_csv = df.round(1).applymap(mark_high_values)
    csv_path = os.path.join(script_dir, "dockerfile_similarity_matrix.csv")
    df_csv.to_csv(csv_path, index=True)
    print(f"\n💾 Saved similarity matrix with highlights to '{csv_path}'")

    # --- Print common code blocks and diffs for highly similar files ---
    print("\n=== 🔍 Detailed Comparison for High Similarities (≥ 85%) ===")
    for f1, f2 in itertools.combinations(df.columns, 2):
        sim_val = df.at[f1, f2]
        if 85 <= sim_val < 100:
            print(f"\n🟢 {f1} ↔ {f2} — Similarity: {green(f'{sim_val:.1f}%')}")
            # Retrieve the full paths for the pair
            path1 = os.path.join(folder, f1)
            path2 = os.path.join(folder, f2)
            blocks = common[(path1, path2)]
            if not blocks:
                print("   (No significant common blocks found)")
            else:
                print(green("   Common Blocks:"))
                for i, block in enumerate(blocks, 1):
                    print(green(f"   Block {i}:"))
                    print(green("   " + "\n   ".join(block)))

            print(red("\n   🔻 Differences:"))
            show_diff(contents[path1], contents[path2], f1, f2)
