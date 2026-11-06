import time
from pathlib import Path

from gradio_client import Client, handle_file

ROOT = Path(__file__).resolve().parent.parent

person_path = Path(r"C:\Users\Hp\.gemini\antigravity\brain\86952866-9b7f-47c5-8a58-9e5a4313d53a\.user_uploaded\media_1793962756382_08b90656.jpg")
garment_path = ROOT / "garments" / "raw" / "grey_hoodie.jpg"

print(f"Person exists: {person_path.exists()}")
print(f"Garment exists: {garment_path.exists()}")

print("Connecting to yisol/IDM-VTON space...")
client = Client("yisol/IDM-VTON")
print("Submitting tryon job...")

t0 = time.time()
try:
    result = client.predict(
        dict={"background": handle_file(str(person_path)), "layers": [], "composite": None},
        garm_img=handle_file(str(garment_path)),
        garment_des="grey hoodie",
        is_checked=True,
        is_checked_crop=False,
        denoise_steps=20,
        seed=42,
        api_name="/tryon"
    )
    t1 = time.time()
    print(f"Job completed in {t1 - t0:.2f}s!")
    print("Result:", result)
except (RuntimeError, ValueError, OSError) as e:
    print("Error during predict:", e)
