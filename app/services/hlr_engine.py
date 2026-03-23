import math

class HLREngine:
    def __init__(self):
        # 边界约束 (论文要求：15分钟 ~ 9个月)
        self.MIN_HALF_LIFE = 15.0 / (60.0 * 24.0)  # 约 0.0104 天
        self.MAX_HALF_LIFE = 270.0               # 270 天
        
        # 启发式权重矩阵 (模拟论文中的 Theta 参数)
        self.theta_correct = 1.2   # 每次答对，半衰期指数增加的权重
        self.theta_wrong = -0.8    # 每次答错，半衰期指数减少的权重

    def calculate_half_life(self, x_correct: int, x_wrong: int, base_difficulty: float) -> float:
        """
        计算半衰期 h = 2^(Theta * x)
        base_difficulty: 由 LLM 提供的该语言点的初始难度先验值 (相当于特征工程的截距)
        """
        # 计算特征向量的点积
        theta_x = (self.theta_correct * x_correct) + (self.theta_wrong * x_wrong) - base_difficulty
        
        # 计算半衰期 h (单位：天)
        h = math.pow(2.0, theta_x)
        
        # 边界裁剪 (防止溢出或过度衰减)
        return max(self.MIN_HALF_LIFE, min(self.MAX_HALF_LIFE, h))

    def predict_recall_probability(self, h: float, delta_days: float) -> float:
        """
        预测召回率 p = 2^(-Delta / h)
        delta_days: 距离上次复习过去的天数
        """
        if delta_days <= 0:
            return 1.0 # 刚学完，或还没过时间，记忆率为 100%
        
        p = math.pow(2.0, -delta_days / h)
        return p
