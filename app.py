"""
Streamlit 画像ギャラリー

前提:
  pip install streamlit pillow

実行:
  streamlit run app.py -- [-d base_dir]
"""
import os
import time
import hashlib
from pathlib import Path
from typing import List, Tuple
import argparse

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"}
THUMB_SIZE = (320, 320)
THUMB_DIRNAME = ".thumbnails"

st.set_page_config(page_title="画像ギャラリー", layout="wide")
st.markdown(
    """
<style>
header {
    background-color: transparent !important;
}
.stDialog>div {
    padding-top: 0;
    transition-duration: 0;
}
.stDialog .stVerticalBlock {
    gap: 0.5rem;
}
div[role="dialog"] {
    margin: 0 !important;
}
div[role="dialog"]>div:first-child {
    display: none !important;
}
div[role="dialog"]>div:nth-child(2) {
    padding: 0.75rem !important;
}
div[role="dialog"]>button {
    top: 1.5rem !important;
}
.element-container:has(iframe) {
    display: none;
}
</style>
    """,
    unsafe_allow_html=True
)


# --------------------
# Helpers
# --------------------
def list_subdirs(base: Path) -> List[Path]:
    try:
        return sorted([p for p in base.iterdir() if p.is_dir()])
    except Exception:
        return []


def list_images(dirpath: Path) -> List[Tuple[Path, float]]:
    out = []
    try:
        for p in dirpath.iterdir():
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                out.append((p, p.stat().st_mtime))
    except Exception:
        pass
    return out


def ensure_thumb_dir(dirpath: Path) -> Path:
    td = dirpath / THUMB_DIRNAME
    td.mkdir(exist_ok=True)
    return td


def thumb_path_for(image_path: Path, thumb_dir: Path) -> Path:
    """
    Use a stable hash-based filename for thumbnails and always use .jpg so
    all thumbnails have the same format and dimensions.
    """
    h = hashlib.sha1(str(image_path.resolve()).encode("utf-8")).hexdigest()
    return thumb_dir / f"{h}.jpg"


def generate_thumbnail_if_needed(image_path: Path, thumb_path: Path, size=THUMB_SIZE) -> Path:
    """
    Create a thumbnail that exactly matches `size` by:
      - resizing the source image to fit within size while preserving aspect ratio
      - creating a fixed-size RGB canvas (white background)
      - pasting the resized image centered on the canvas
      - saving as JPEG to thumb_path
    This ensures all thumbnails have identical dimensions so the grid stays aligned.
    """
    try:
        # If the thumb exists and is up-to-date, reuse it
        if thumb_path.exists() and thumb_path.stat().st_mtime >= image_path.stat().st_mtime:
            return thumb_path

        with Image.open(image_path) as img:
            # Convert to RGB to ensure consistent JPEG saving (handles RGBA/LA)
            img = img.convert("RGBA")

            # Compute target size preserving aspect ratio
            src_w, src_h = img.size
            target_w, target_h = size
            ratio = min(target_w / src_w, target_h / src_h)
            new_w = max(1, int(src_w * ratio))
            new_h = max(1, int(src_h * ratio))
            resized = img.resize((new_w, new_h), resample=Image.LANCZOS)

            # Create white background canvas (RGB) and paste centered
            canvas = Image.new("RGB", size, (255, 255, 255))
            # If the resized image has alpha, composite onto white background first
            if resized.mode in ("RGBA", "LA") or ("transparency" in resized.info):
                bg = Image.new("RGBA", resized.size, (255, 255, 255, 255))
                bg.paste(resized, (0, 0), resized)
                resized_rgb = bg.convert("RGB")
            else:
                resized_rgb = resized.convert("RGB")

            offset_x = (target_w - new_w) // 2
            offset_y = (target_h - new_h) // 2
            canvas.paste(resized_rgb, (offset_x, offset_y))

            # Ensure directory exists and save as JPEG
            thumb_path.parent.mkdir(parents=True, exist_ok=True)
            canvas.save(thumb_path, format="JPEG", quality=85, optimize=True)

        # Set thumb mtime to match source so update logic works
        try:
            os.utime(thumb_path, (time.time(), image_path.stat().st_mtime))
        except Exception:
            pass

        return thumb_path
    except Exception:
        # On failure, fall back to original image path so UI still shows something
        return image_path


def delete_paths(paths: List[str]) -> Tuple[List[str], List[Tuple[str, str]]]:
    successes: List[str] = []
    failures: List[Tuple[str, str]] = []
    for p in paths:
        try:
            os.remove(p)
            successes.append(p)
        except Exception as e:
            failures.append((p, str(e)))
    return successes, failures


# チェックボックスのON/OFFをキビキビ動かすためのworkaround
def checkbox_on_change(i: int):
    def f():
        st.session_state.checked[str(i)] = st.session_state[f"raw_checked_{i}"]
    return f


# dialogを閉じたときに確実にsessionもクリアする
def show_preview_on_dismiss():
    st.session_state.preview_index = -1
def confirm_delete_on_dismiss():
    st.session_state.to_delete = []


# --------------------
# Session state init
# --------------------
if "preview_index" not in st.session_state:
    st.session_state.preview_index = -1
if "to_delete" not in st.session_state:
    st.session_state.to_delete = []
if "checked" not in st.session_state:
    st.session_state.checked = {}


# --------------------
# Sidebar / settings
# --------------------
st.sidebar.title("設定")

parser = argparse.ArgumentParser()
parser.add_argument('--base-dir', '-d', type=str, default='.')
args = parser.parse_args()

base_dir = Path(args.base_dir).expanduser()
if not base_dir.exists() or not base_dir.is_dir():
    st.sidebar.error("指定されたディレクトリが見つかりません。")
    st.stop()

subdirs = list_subdirs(base_dir)
if not subdirs:
    st.sidebar.info("起点ディレクトリにサブディレクトリがありません。")
    st.stop()

selected_subdir = st.sidebar.selectbox("サブディレクトリを選択", ["."] + [p.name for p in subdirs])
target_dir = base_dir / selected_subdir

sort_by = st.sidebar.selectbox("並び替え", ["名前 (昇順)", "名前 (降順)", "更新日時 (新しい順)", "更新日時 (古い順)"], 1)
cols_per_row = st.sidebar.slider("1行当たりの項目数", 1, 6, 4)

images = list_images(target_dir)

if sort_by == "名前 (昇順)":
    images.sort(key=lambda x: x[0].name.lower())
elif sort_by == "名前 (降順)":
    images.sort(key=lambda x: x[0].name.lower(), reverse=True)
elif sort_by == "更新日時 (新しい順)":
    images.sort(key=lambda x: x[1], reverse=True)
else:
    images.sort(key=lambda x: x[1])

if st.sidebar.button("リロード"):
    st.rerun()

st.sidebar.markdown("---")

with st.sidebar.container():
    c1, c2 = st.sidebar.columns([1, 1])
    with c1:
        if st.button("全選択"):
            for i, _ in enumerate(images):
                st.session_state.checked[str(i)] = True
            # rerunしないとcheckboxに反映されないことがある
            st.rerun()
    with c2:
        if st.button("全解除"):
            st.session_state.checked = {}
            # rerunしないとcheckboxに反映されないことがある
            st.rerun()
    cnt = sum([1 if v else 0 for _, v in st.session_state.checked.items()])
    if st.sidebar.button(f"{cnt}件を削除"):
        to_delete = []
        for k, v in st.session_state.checked.items():
            if v:
                p = images[int(k)][0]
                to_delete.append(str(p))
        if len(to_delete) > 0:
            st.session_state.to_delete = to_delete
        else:
            st.sidebar.info("削除する画像が選択されていません。")


# --------------------
# Main gallery UI
# --------------------
st.markdown(f"## ギャラリー `{selected_subdir}`")

if not images:
    st.info("このディレクトリに表示条件に合う画像が見つかりません。")
else:
    # image grid
    thumb_dir = ensure_thumb_dir(target_dir)
    columns = st.columns(cols_per_row)
    
    for img_i, (img_p, _) in enumerate(images):
        column = columns[img_i % cols_per_row]
        thumb = generate_thumbnail_if_needed(img_p, thumb_path_for(img_p, thumb_dir))
        with column:
            st.image(str(thumb), use_container_width=True, caption=img_p.name)
            key = f"raw_checked_{img_i}"
            value = st.session_state.checked.get(str(img_i))
            st.checkbox("選択", key=key, value=value, on_change=checkbox_on_change(img_i))
            b1, b2 = st.columns([1, 1])
            with b1:
                if st.button("拡大", key=f"preview_{img_i}"):
                    st.session_state.preview_index = img_i
            with b2:
                if st.button("削除", key=f"delete_{img_i}"):
                    to_delete = [str(img_p)]
                    st.session_state.to_delete = to_delete


# --------------------
# Dialogs
# --------------------
@st.dialog("プレビュー", width="medium", on_dismiss=show_preview_on_dismiss)
def show_preview():
    if "preview_index" in st.session_state:
        img_i = int(st.session_state.preview_index)
        img_p = images[img_i][0]
        st.image(img_p)
        st.write(f"パス: {img_p}")
        [c1, c2, c3] = st.columns([1, 1, 1])
        with c1:
            if st.button("⏪️ J"):
                if img_i - 1 >= 0:
                    st.session_state.preview_index = img_i - 1
                    # rerunした方が切替がスムーズ
                    st.rerun(scope="fragment")
        with c2:
            if st.button("⏩️ K"):
                if img_i + 1 < len(images):
                    st.session_state.preview_index = img_i + 1
                    # rerunした方が切替がスムーズ
                    st.rerun(scope="fragment")
        with c3:
            if st.button("削除 (この画像のみ)", key="dialog_delete"):
                to_delete = [str(img_p)]
                st.session_state.to_delete = to_delete
                st.session_state.preview_index = -1
                st.rerun()
    
    components.html(
        """
<script>
const doc = window.parent.document;
const buttons = Array.from(doc.querySelectorAll('button[kind=secondary]'));
const prev_button = buttons.find(el => el.innerText === '⏪️ J');
const next_button = buttons.find(el => el.innerText === '⏩️ K');
doc.addEventListener('keydown', function(e) {
    switch (e.keyCode) {
        case 74: // j
            prev_button.click();
            break;
        case 75: // k
            next_button.click();
            break;
    }
});
</script>
        """,
        width=0,
        height=0
    )


@st.dialog("削除確認", on_dismiss=confirm_delete_on_dismiss)
def confirm_delete():
    to_delete = st.session_state.to_delete or []
    to_delete = to_delete[:200]
    st.warning(f"本当に削除しますか？ {len(to_delete)} 件の画像が削除されます。これは元に戻せません。")
    for p in to_delete:
        st.write(p)
    if st.button("削除を実行", key="dialog_confirm"):
        successes, failures = delete_paths(to_delete)
        if successes:
            st.success(f"削除しました: {len(successes)} 件")
        if failures:
            for p, err in failures:
                st.error(f"削除失敗: {p} — {err}")
        st.session_state.checked = {}
        st.session_state.to_delete = []
        st.rerun()


# show_preview -> confirm_deleteの遷移を可能にするため、
# dialogの表示状態をsession管理にしている
if st.session_state.preview_index >= 0:
    show_preview()
if len(st.session_state.to_delete) > 0:
    confirm_delete()


# --------------------
# Footer
# --------------------
st.sidebar.markdown("---")
st.sidebar.markdown("実装: [streamlit-photo-gallery](https://github.com/tondol/streamlit-photo-gallery)")
