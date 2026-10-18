import os
import shutil
import subprocess
import uuid
from pathlib import Path
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename

APP_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = APP_DIR / "uploads"
OUTPUT_DIR = APP_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ganti-secret-key-ini")
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024  # batas upload 300 MB
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}

def ffmpeg_path():
    return shutil.which("ffmpeg")

@app.errorhandler(413)
def too_large(_):
    flash("File terlalu besar. Maksimal 300 MB.")
    return redirect(url_for("index"))

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        uploaded = request.files.get("video")
        if not uploaded or not uploaded.filename:
            flash("Pilih video terlebih dahulu.")
            return redirect(url_for("index"))
        ext = Path(secure_filename(uploaded.filename)).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            flash("Format tidak didukung. Gunakan MP4, MOV, M4V, WEBM, atau MKV.")
            return redirect(url_for("index"))
        if not ffmpeg_path():
            flash("FFmpeg belum terpasang di server. Pasang FFmpeg lalu jalankan ulang.")
            return redirect(url_for("index"))

        resolution = request.form.get("resolution", "1080x1920")
        fps = request.form.get("fps", "30")
        quality = request.form.get("quality", "high")
        # Pilihan dibatasi agar pengguna tidak dapat menyisipkan perintah FFmpeg.
        allowed_res = {"1080x1920", "720x1280", "1080x1080", "1920x1080"}
        allowed_fps = {"24", "30", "60"}
        allowed_quality = {"standard", "high", "veryhigh"}
        if resolution not in allowed_res or fps not in allowed_fps or quality not in allowed_quality:
            flash("Pengaturan tidak valid.")
            return redirect(url_for("index"))

        job = uuid.uuid4().hex
        input_path = UPLOAD_DIR / f"{job}{ext}"
        output_path = OUTPUT_DIR / f"KIMPUL_MTD_{job[:8]}.mp4"
        uploaded.save(input_path)

        crf = {"standard": "23", "high": "20", "veryhigh": "18"}[quality]
        # Mempertahankan rasio aspek, menyesuaikan kanvas, dan menghindari peregangan.
        vf = (
            f"scale={resolution.split('x')[0]}:{resolution.split('x')[1]}:"
            "force_original_aspect_ratio=decrease:force_divisible_by=2,"
            f"pad={resolution.split('x')[0]}:{resolution.split('x')[1]}:(ow-iw)/2:(oh-ih)/2,"
            f"fps={fps},setsar=1"
        )
        cmd = [
            ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(input_path), "-vf", vf,
            "-c:v", "libx264", "-preset", "medium", "-crf", crf,
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", "-max_muxing_queue_size", "1024",
            str(output_path)
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            if result.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
                err = (result.stderr or "Proses FFmpeg gagal.")[-700:]
                flash("Gagal memproses video. " + err)
                return redirect(url_for("index"))
            return send_file(output_path, as_attachment=True, download_name="KIMPUL_MTD_FHD.mp4")
        except subprocess.TimeoutExpired:
            flash("Proses melewati batas waktu 30 menit. Coba video lebih pendek.")
            return redirect(url_for("index"))
        finally:
            try:
                input_path.unlink(missing_ok=True)
            except Exception:
                pass
    return render_template("index.html")

if __name__ == "__main__":
    # Untuk penggunaan lokal. Hosting publik menjalankan Gunicorn.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
