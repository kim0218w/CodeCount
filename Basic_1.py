# 사용자로부터 입력을 받음 (input은 기본적으로 문자열로 저장됨)
celsius_input = input("섭씨온도를 입력하세요 (°C): ")

# 문자열을 실수(float) 형태로 변환
celsius = float(celsius_input)

# 섭씨를 화씨로 변환하는 공식 적용
fahrenheit = (celsius * 9 / 5) + 32

# f-string을 활용한 출력 (소수점 둘째 자리까지 표시)
print(f"섭씨 {celsius}°C는 화씨 {fahrenheit:.2f}°F 입니다.")
########################################################
# 점수 입력받기
score = int(input("점수를 입력하세요 (0~100): "))

# 입력받은 점수 범위 검증 및 학점 판별
if score < 0 or score > 100:
    print("잘못된 점수입니다. 0에서 100 사이의 숫자를 입력해주세요.")
elif score >= 90:
    grade = "A"
elif score >= 80:
    grade = "B"
elif score >= 70:
    grade = "C"
elif score >= 60:
    grade = "D"
else:
    grade = "F"

if 0 <= score <= 100:
    print(f"입력한 점수: {score}점 -> 학점: {grade}")

########################################################
import random

# 1부터 20 사이의 난수(임의의 숫자) 생성
target_number = random.randint(1, 20)
attempts = 0

print("=== 1부터 20 사이의 숫자를 맞춰보세요! ===")

while True:
    guess = int(input("숫자 입력: "))
    attempts += 1  # 시도 횟수 증가

    if guess < target_number:
        print("UP! 더 큰 숫자입니다.")
    elif guess > target_number:
        print("DOWN! 더 작은 숫자입니다.")
    else:
        print(f"축하합니다! {attempts}번 만에 맞추셨습니다 🎉")
        break  # 정답을 맞추면 반복문 탈출
#######################################################

    # 단어장 데이터 (Dictionary)
voca_dict = {
    "apple": "사과",
    "banana": "바나나",
    "python": "파이썬"
}

# 단어 추가 함수
def add_word(word, meaning):
    voca_dict[word] = meaning
    print(f"단어 '{word}'이(가) 추가되었습니다.")

# 단어 검색 함수
def search_word(word):
    if word in voca_dict:
        print(f"-> {word}: {voca_dict[word]}")
    else:
        print(f"-> '{word}'은(는) 단어장에 없습니다.")

# 함수 호출 및 테스트
search_word("apple")
add_word("computer", "컴퓨터")
search_word("computer")
########################################################
file_name = "memo.txt"

# 1. 파일에 내용 쓰기 ('w' 모드)
with open(file_name, "w", encoding="utf-8") as file:
    file.write("=== 나의 첫 파이썬 메모장 ===\n")
    file.write("1. 파이썬 기초 공부하기\n")
    file.write("2. OpenCV 예제 실습하기\n")

print(f"'{file_name}' 파일에 내용이 성공적으로 저장되었습니다.\n")

# 2. 저장된 파일 내용 읽기 ('r' 모드)
print("--- 저장된 파일 내용 ---")
with open(file_name, "r", encoding="utf-8") as file:
    content = file.read()
    print(content)
########################################################
