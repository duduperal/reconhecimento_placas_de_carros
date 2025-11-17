# car_plate_recognition.py
import cv2
import numpy as np
import pytesseract
import re
import time
from datetime import datetime

# ---------- CONFIGURAÇÕES ----------
# Se estiver no Windows, defina o caminho do tesseract, exemplo:
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# Se não precisar, comente a linha abaixo.
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Config do Tesseract: usar psm 7 (uma linha de texto) e whitelist (apenas letras e números)
TESSERACT_CONFIG = '--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'


# Regex para filtrar placa brasileira (padrão antigo AAA9999 ou padrão Mercosul AAA9A99)
# Ajuste conforme país. Aqui tentamos aceitar sequências alfanuméricas com 5-8 caracteres.
PLATE_REGEX = re.compile(r'([A-Z0-9]{5,8})')

# Salvar imagens detectadas em 'captures/' quando for detectada uma placa
SAVE_CAPTURES = True
CAPTURE_DIR = "captures"

# ---------- FUNÇÕES AUXILIARES ----------
def clean_text(text):
    """Remove caracteres indesejados e retorna uppercase."""
    if not text:
        return ""
    text = text.upper()
    # Remove tudo que não for alfanumérico
    text = re.sub(r'[^A-Z0-9]', '', text)
    return text

def is_valid_plate(text):
    """Valida texto encontrado com regex simples."""
    if not text:
        return False
    m = PLATE_REGEX.search(text)
    return bool(m)

def preprocess_plate(img_gray):
    """Melhora contraste e binariza para OCR com menos ruído."""
    # aumenta contraste com CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    cl = clahe.apply(img_gray)

    # redução de ruído
    bl = cv2.bilateralFilter(cl, 11, 90, 90)

    # binarização forte (OTSU)
    _, th = cv2.threshold(bl, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # erosão/dilatação para melhorar contornos
    kernel = np.ones((2,2), np.uint8)
    proc = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)
    return proc


def detect_plate_candidates(frame):
    """Detecta regiões candidatas a placa via contornos e filtros de proporção."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # equalizar e reduzir ruído
    gray = cv2.GaussianBlur(gray, (5,5), 0)
    edged = cv2.Canny(gray, 100, 200)

    contours, _ = cv2.findContours(edged, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    h_img, w_img = gray.shape

    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(approx)
            if w < 60 or h < 15:  # muito pequeno
                continue
            aspect_ratio = w / float(h)
            # placa tende a ter razão largura/altura entre ~2 e ~6 (ajuste se necessário)
            if 2.0 < aspect_ratio < 6.5:
                # filtrar por posição (não muito próximo das bordas)
                if x > 5 and y > 5 and (x + w) < (w_img - 5) and (y + h) < (h_img - 5):
                    candidates.append((x, y, w, h))
    return candidates

# ---------- MAIN ----------
def main():
    import os
    if SAVE_CAPTURES:
        os.makedirs(CAPTURE_DIR, exist_ok=True)

    cap = cv2.VideoCapture(0)  # índice 0 normalmente é webcam integrada
    if not cap.isOpened():
        print("Erro: não foi possível abrir a webcam. Verifique o índice (0/1) ou drivers.")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)


    fps_timer = time.time()
    frame_count = 0

    print("Pressione ESC para sair. A janela aparecerá com o vídeo.")
    last_text = ""
    text_counter = 0
    stable_text = ""

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Frame inválido — encerrando.")
            break
        frame_count += 1

        orig = frame.copy()
        candidates = detect_plate_candidates(frame)

        plates_found = []
        for (x, y, w, h) in candidates:
            roi = orig[y:y+h, x:x+w]
            # converter para cinza e pré-processar
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            proc = preprocess_plate(gray_roi)

            # OCR com tesseract
            ocr_result = pytesseract.image_to_string(proc, config=TESSERACT_CONFIG)
            cleaned = clean_text(ocr_result)

            if is_valid_plate(cleaned):
                # estabilidade: só aceita se aparecer igual por alguns frames seguidos
                if cleaned == last_text:
                    text_counter += 1
                else:
                    text_counter = 0
                last_text = cleaned

                if text_counter >= 3:  # apareceu igual por 3 frames
                    stable_text = cleaned

                plates_found.append((cleaned, (x,y,w,h)))
                cv2.rectangle(frame, (x,y), (x+w, y+h), (0,255,0), 2)
                cv2.putText(frame, stable_text if stable_text else cleaned, (x, y-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,255,0), 2)


                # opcional: salvar captura
                if SAVE_CAPTURES:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    fname = f"{CAPTURE_DIR}/plate_{cleaned}_{ts}.png"
                    cv2.imwrite(fname, orig)
                    print(f"[SALVO] {fname}")

        # mostrar aviso se nada detectado (opcional)
        if not plates_found:
            cv2.putText(frame, "Nenhuma placa detectada", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)

        # mostrar FPS aproximado
        if time.time() - fps_timer >= 1.0:
            fps = frame_count / (time.time() - fps_timer)
            fps_timer = time.time()
            frame_count = 0
        else:
            fps = None
        if fps:
            cv2.putText(frame, f"FPS: {int(fps)}", (10, frame.shape[0]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,0), 2)

        cv2.imshow("Reconhecimento de Placas - Pressione ESC para sair", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Encerrado.")

if __name__ == "__main__":
    main()
