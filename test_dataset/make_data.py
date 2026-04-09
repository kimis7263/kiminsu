import pandas as pd
import numpy as np
import os

# 1000 스텝짜리 가짜 AI 로그 생성
steps = np.arange(1, 1001)

# Loss는 점점 줄어들게, Accuracy는 점점 오르게 (약간의 노이즈 추가)
train_loss = 3.0 * np.exp(-steps / 200) + np.random.normal(0, 0.05, 1000)
val_loss = 2.8 * np.exp(-steps / 200) + np.random.normal(0, 0.1, 1000)
# Val Loss는 후반부에 오버피팅 느낌으로 살짝 띄우기
val_loss[500:] += np.linspace(0, 0.5, 500) 

accuracy = 0.1 + 0.85 * (1 - np.exp(-steps / 300)) + np.random.normal(0, 0.02, 1000)

# DataFrame 생성 및 CSV 저장
df = pd.DataFrame({
    'Step': steps,
    'Train_Loss': train_loss,
    'Val_Loss': val_loss,
    'Accuracy': accuracy
})

df.to_csv('massive_test_log_2.csv', index=False)
print("✅ massive_test_log.csv 생성 완료! 프로그램을 켜서 폴더를 선택해 보세요!")