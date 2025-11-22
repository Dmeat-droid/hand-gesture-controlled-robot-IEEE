import cv2
import mediapipe as mp
import math
import socket
import time

# --- KONFIGURASI ---
UDP_IP = "192.168.248.132"
UDP_PORT = 4210
SEND_DELAY = 0.05 

# Range Jarak Jari (dalam Pixel) untuk kalibrasi gas
# Sesuaikan ini nanti dengan jarak tanganmu ke kamera
MIN_FINGER_DIST = 30   # Posisi mencubit (Speed 0)
MAX_FINGER_DIST = 200  # Posisi terbuka lebar (Speed Maks)
# -------------------

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
print(f"UDP ready to send to {UDP_IP}:{UDP_PORT}")

last_command = ""
last_send_time = 0

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False,
                      max_num_hands=1,
                      min_detection_confidence=0.6,
                      min_tracking_confidence=0.6)
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

cap = cv2.VideoCapture(0)

def send_udp(command):
    """Mengirim perintah string, misal 'F:255' atau 'L:150'"""
    global last_command, last_send_time
    current_time = time.time()
    
    # Kirim jika waktu delay lewat ATAU jika perintah berubah drastis (misal dari F ke L)
    # Kita ambil karakter pertama saja untuk cek perubahan tipe perintah (F/L/R/B/S)
    cmd_type = command.split(':')[0]
    last_cmd_type = last_command.split(':')[0] if ':' in last_command else last_command

    if (current_time - last_send_time >= SEND_DELAY) or (cmd_type != last_cmd_type):
        try:
            sock.sendto(command.encode(), (UDP_IP, UDP_PORT))
            last_command = command
            last_send_time = current_time
            # print(f"Sent: {command}") # Uncomment untuk debug
            return True
        except Exception as e:
            print(f"Send error: {e}")
    return False

def calculate_speed(p4, p8, w, h, image):
    """Menghitung kecepatan berdasarkan jarak Jempol (4) dan Telunjuk (8)"""
    x1, y1 = int(p4.x * w), int(p4.y * h)
    x2, y2 = int(p8.x * w), int(p8.y * h)
    
    # 1. Hitung Jarak Euclidean (Pytagoras)
    distance = math.hypot(x2 - x1, y2 - y1)
    
    # 2. Visualisasi Garis Gas
    cv2.line(image, (x1, y1), (x2, y2), (0, 255, 255), 3) # Garis Kuning
    cv2.circle(image, (x1, y1), 5, (0, 255, 255), cv2.FILLED)
    cv2.circle(image, (x2, y2), 5, (0, 255, 255), cv2.FILLED)
    
    # 3. Mapping Jarak (Pixel) ke PWM (0 - 255)
    # Rumus manual interpolasi
    if distance < MIN_FINGER_DIST:
        speed = 0
    elif distance > MAX_FINGER_DIST:
        speed = 255
    else:
        # (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
        speed = (distance - MIN_FINGER_DIST) * (255 - 0) / (MAX_FINGER_DIST - MIN_FINGER_DIST) + 0
    
    return int(speed), distance

def draw_speed_bar(image, speed):
    """Menggambar Bar Kecepatan di pinggir layar"""
    h, w, _ = image.shape
    bar_h = int((speed / 255) * 200) # Tinggi bar maks 200px
    
    # Kotak luar
    cv2.rectangle(image, (w - 50, h - 250), (w - 20, h - 50), (0, 255, 0), 2)
    # Isi bar (makin cepat makin tinggi)
    cv2.rectangle(image, (w - 50, h - 50 - bar_h), (w - 20, h - 50), (0, 255, 0), cv2.FILLED)
    cv2.putText(image, f"{speed}", (w - 60, h - 255), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

# ... (Fungsi calculate_angle dan is_fist SAMA SEPERTI SEBELUMNYA) ...
def calculate_angle(point1, point2, image, w, h):
    x1, y1 = int(point1.x * w), int(point1.y * h)
    x2, y2 = int(point2.x * w), int(point2.y * h)
    dx = point2.x - point1.x
    dy = point2.y - point1.y
    angle = math.degrees(math.atan2(dx, -dy))
    cv2.line(image, (x1, y1), (x2, y2), (255, 0, 0), 3)
    return angle

def is_fist(landmarks):
    wrist = landmarks[0]
    fingers = [(8, 6), (12, 10), (16, 14), (20, 18)]
    folded_count = 0
    for tip_idx, pip_idx in fingers:
        tip = landmarks[tip_idx]
        pip = landmarks[pip_idx]
        if math.hypot(tip.x - wrist.x, tip.y - wrist.y) < math.hypot(pip.x - wrist.x, pip.y - wrist.y):
            folded_count += 1
    return folded_count >= 3

def main():
    while cap.isOpened():
        success, image = cap.read()
        if not success: continue

        image = cv2.flip(image, 1)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = hands.process(image_rgb)
        h, w, _ = image.shape

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(
                    image, hand_landmarks, mp_hands.HAND_CONNECTIONS,
                    mp_drawing_styles.get_default_hand_landmarks_style(),
                    mp_drawing_styles.get_default_hand_connections_style())
                
                landmarks = hand_landmarks.landmark
                wrist = landmarks[0]
                middle_mcp = landmarks[9]
                thumb_tip = landmarks[4] # JEMPOL
                index_tip = landmarks[8] # TELUNJUK

                # --- HITUNG KECEPATAN (THROTTLE) ---
                speed, dist = calculate_speed(thumb_tip, index_tip, w, h, image)
                draw_speed_bar(image, speed) # Gambar UI Speedometer

                # --- LOGIKA KONTROL ---
                if is_fist(landmarks):
                    cv2.putText(image, "STOP", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
                    send_udp('S:0') # Stop speed 0

                else:
                    angle = calculate_angle(wrist, middle_mcp, image, w, h)
                    angle = angle + 12
                    
                    # Kirim format perintah: "COMMAND:SPEED"
                    if angle > 120 or angle < -120:
                        cv2.putText(image, f"BACK {speed}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 165, 255), 3)
                        send_udp(f'B:{speed}')
                        
                    elif angle < -25:
                        cv2.putText(image, f"LEFT {speed}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        send_udp(f'L:{speed}')
                        
                    elif angle > 25:
                        cv2.putText(image, f"RIGHT {speed}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        send_udp(f'R:{speed}')
                        
                    else:
                        cv2.putText(image, f"FWD {speed}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        send_udp(f'F:{speed}')

        else:
            cv2.putText(image, "NO HAND", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            send_udp('S:0')

        cv2.imshow('Awisy RC Pro Control', image)
        if cv2.waitKey(5) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    try: sock.sendto('S:0'.encode(), (UDP_IP, UDP_PORT)) 
    except: pass

if __name__ == "__main__":
    main()