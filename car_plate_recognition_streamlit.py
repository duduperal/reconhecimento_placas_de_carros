import streamlit as st
import cv2
import pytesseract
import numpy as np
from PIL import Image
import time

# -- CONFIG STREAMLIT --
st.set_page_config(page_title="Reconhecimento de Placas", layout="wide")

# -- CONFIG TESSERACT --
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

OCR_CONFIG = "--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

def clean_text(t):
    import re
    t = t.upper()
    return re.sub(r'[^A-Z0-9]', '', t)

# -- DETECÇÃO SIMPLIFICADA --
def detect_plate(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5,5), 0)
    edges = cv2.Canny(blur, 100, 200)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    for c in contours:
        approx = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
        if len(approx) == 4:
            x,y,w,h = cv2.boundingRect(approx)
            if w < 60 or h < 15: 
                continue

            roi = gray[y:y+h, x:x+w]
            _, th = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            text = pytesseract.image_to_string(th, config=OCR_CONFIG)
            text = clean_text(text)

            if 5 <= len(text) <= 7:
                cv2.rectangle(frame, (x,y), (x+w,y+h), (0,255,0), 2)
                cv2.putText(frame, text, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
                return frame, text

    return frame, ""

# -- CAPTURA DA WEBCAM (SEM WHILE) --
st.title("Reconhecimento de Placas em Tempo Real")

frame_area = st.empty()
text_area = st.empty()

cap = cv2.VideoCapture(0)
cap.set(3, 640)
cap.set(4, 360)

# Roda 1 frame a cada atualização
while True:
    ret, frame = cap.read()
    if not ret:
        st.error("Erro ao capturar vídeo da webcam")
        break

    frame, text = detect_plate(frame)

    # Converte e exibe
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    frame_area.image(frame_rgb, channels="RGB")

    if text:
        text_area.markdown(f"### Placa detectada: **{text}**")
    else:
        text_area.markdown("Nenhuma placa detectada")

    time.sleep(0.03)  # 30 FPS aproximado
