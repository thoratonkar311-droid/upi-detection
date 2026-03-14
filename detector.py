import cv2
import pytesseract
import re
import hashlib
import csv
import os
import shutil
from PIL import Image, ImageChops


# -------------------------------
# AUTO DETECT TESSERACT PATH
# -------------------------------
tesseract_path = shutil.which("tesseract")

if tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = tesseract_path


seen_hashes = set()


# -------------------------------
# IMAGE DIMENSION CHECK
# -------------------------------
def check_dimensions(image):

    h, w = image.shape[:2]

    return {
        "width": w,
        "height": h,
        "valid": w >= 700 and h >= 1200
    }


# -------------------------------
# CROP DETECTION
# -------------------------------
def detect_crop(image):

    h, w = image.shape[:2]

    ratio = h / w

    return ratio < 1.5


# -------------------------------
# IMPROVED IMAGE PREPROCESSING
# -------------------------------
def preprocess(image):

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,
        2
    )

    return thresh


# -------------------------------
# OCR WITH CONFIDENCE FILTER
# -------------------------------
def extract_text_with_confidence(image):

    custom_config = r'--oem 3 --psm 6'

data = pytesseract.image_to_data(
    image,
    config=custom_config,
    output_type=pytesseract.Output.DICT
)

    text = ""

    for i in range(len(data["text"])):

        try:
            conf = int(data["conf"][i])
        except:
            conf = 0

        if conf > 60:
            text += data["text"][i] + "\n"

    return text


# -------------------------------
# IMPROVED TEXT EXTRACTION
# -------------------------------
def extract_details(text):

    upi_pattern = r"[a-zA-Z0-9._]+@[a-zA-Z]+"

    amount_pattern = r"₹?\s?\d+[,\d]*(?:\.\d+)?"

    txn_pattern = r"[A-Z0-9]{8,}"

    upi = re.findall(upi_pattern, text)

    amount = re.findall(amount_pattern, text)

    txn = re.findall(txn_pattern, text)

    name = "Unknown"

    lines = text.split("\n")

    for line in lines:

        line = line.strip()

        if (
            len(line) > 4
            and len(line) < 30
            and not any(x in line.lower() for x in [
                "google",
                "phonepe",
                "paytm",
                "upi",
                "transaction",
                "₹",
                "@",
                "paid"
            ])
        ):

            name = line
            break

    return name, upi, amount, txn


# -------------------------------
# VALIDATE UPI HANDLE
# -------------------------------
valid_handles = [
    "okaxis",
    "oksbi",
    "okicici",
    "ybl",
    "ibl",
    "paytm",
    "upi"
]


def validate_upi(upi_list):

    for u in upi_list:

        if "@" in u:

            bank = u.split("@")[1]

            if bank.lower() in valid_handles:
                return True

    return False


# -------------------------------
# IMAGE TAMPERING DETECTION
# -------------------------------
def detect_editing(image):

    temp = "temp.jpg"

    if image.mode == "RGBA":
        image = image.convert("RGB")

    image.save(temp, "JPEG", quality=90)

    resaved = Image.open(temp)

    diff = ImageChops.difference(image, resaved)

    extrema = diff.getextrema()

    max_diff = max([ex[1] for ex in extrema])

    os.remove(temp)

    return max_diff > 40


# -------------------------------
# NOISE DETECTION
# -------------------------------
def detect_noise(image):

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    laplacian = cv2.Laplacian(gray, cv2.CV_64F)

    variance = laplacian.var()

    return variance < 50


# -------------------------------
# DUPLICATE SCREENSHOT DETECTION
# -------------------------------
def detect_duplicate(image):

    global seen_hashes

    img_hash = hashlib.md5(image.tobytes()).hexdigest()

    if img_hash in seen_hashes:
        return True

    seen_hashes.add(img_hash)

    return False


# -------------------------------
# IMPROVED LOGO DETECTION
# -------------------------------
def detect_upi_app(image):

    apps = {
        "Google Pay": "logos/gpay.png",
        "PhonePe": "logos/phonepe.png",
        "Paytm": "logos/paytm.png"
    }

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    roi = gray[0:300, :]

    detected = "Unknown"

    for app, logo in apps.items():

        template = cv2.imread(logo, 0)

        if template is None:
            continue

        if roi.shape[0] < template.shape[0]:
            continue

        for scale in [0.3, 0.5, 0.7, 1.0, 1.3]:

            resized = cv2.resize(template, None, fx=scale, fy=scale)

            result = cv2.matchTemplate(
                roi,
                resized,
                cv2.TM_CCOEFF_NORMED
            )

            if (result >= 0.5).any():

                detected = app
                return detected

    return detected


# -------------------------------
# FRAUD SCORE
# -------------------------------
def fraud_score(
    upi_valid,
    txn,
    amount,
    editing,
    dimension,
    noise,
    crop,
    duplicate
):

    score = 0

    if not upi_valid:
        score += 40

    if not txn:
        score += 30

    if not amount:
        score += 20

    if editing:
        score += 25

    if noise:
        score += 10

    if crop:
        score += 15

    if duplicate:
        score += 20

    if not dimension["valid"]:
        score += 20

    score = min(score, 100)

    return score


# -------------------------------
# CLASSIFY RESULT
# -------------------------------
def classify_transaction(score):

    if score >= 60:
        return "FAKE"

    elif score >= 30:
        return "SUSPICIOUS"

    else:
        return "REAL"


# -------------------------------
# SAVE RESULT TO CSV
# -------------------------------
def save_to_csv(data, filename="fraud_report.csv"):

    file_exists = os.path.isfile(filename)

    headers = [
        "File Name",
        "Name",
        "UPI App",
        "Fraud Score",
        "Status",
        "UPI Valid",
        "Editing Detected",
        "Duplicate Screenshot"
    ]

    with open(filename, "a", newline="", encoding="utf-8") as file:

        writer = csv.DictWriter(file, fieldnames=headers)

        if not file_exists:
            writer.writeheader()

        writer.writerow(data)
