"""求职状态机 — 管理投递流程的状态转换"""

# 状态定义和合法转换
STATES = [
    "applied",           # 已投递
    "waiting",           # 等待回应 (投递后等待HR处理)
    "no_response",       # 无回应 (超7天未回复，需分析跟进)
    "resume_screening",  # 初筛中
    "written_test",      # 笔试
    "interview_1",       # 一面
    "interview_2",       # 二面
    "interview_3",       # 三面/终面
    "offer",             # 收到Offer
    "accepted",          # 已接受
    "rejected",          # 已拒绝
    "withdrawn",         # 已撤回
]

# 合法状态转换映射
TRANSITIONS = {
    "applied": ["waiting", "rejected", "withdrawn"],
    "waiting": ["no_response", "resume_screening", "written_test", "interview_1", "rejected", "withdrawn"],
    "no_response": ["waiting", "applied", "withdrawn"],
    "resume_screening": ["written_test", "interview_1", "rejected", "withdrawn"],
    "written_test": ["interview_1", "rejected", "withdrawn"],
    "interview_1": ["interview_2", "offer", "rejected", "withdrawn"],
    "interview_2": ["interview_3", "offer", "rejected", "withdrawn"],
    "interview_3": ["offer", "rejected", "withdrawn"],
    "offer": ["accepted", "rejected", "withdrawn"],
    "accepted": [],       # 终态
    "rejected": [],       # 终态
    "withdrawn": [],      # 终态
}

# 状态中文名
STATE_LABELS = {
    "applied": "已投递",
    "waiting": "等待回应",
    "no_response": "无回应",
    "resume_screening": "初筛中",
    "written_test": "笔试",
    "interview_1": "一面",
    "interview_2": "二面",
    "interview_3": "三面/终面",
    "offer": "收到Offer",
    "accepted": "已接受",
    "rejected": "已拒绝",
    "withdrawn": "已撤回",
}

# 状态颜色 (用于前端显示)
STATE_COLORS = {
    "applied": "blue",
    "waiting": "yellow",
    "no_response": "red",
    "resume_screening": "purple",
    "written_test": "orange",
    "interview_1": "cyan",
    "interview_2": "cyan",
    "interview_3": "cyan",
    "offer": "green",
    "accepted": "green",
    "rejected": "red",
    "withdrawn": "gray",
}


class StateMachine:
    """求职状态机"""

    @staticmethod
    def can_transition(from_status: str, to_status: str) -> bool:
        """检查状态转换是否合法"""
        if from_status not in TRANSITIONS:
            return False
        return to_status in TRANSITIONS[from_status]

    @staticmethod
    def get_next_states(status: str) -> list[str]:
        """获取当前状态可转换到的下一个状态列表"""
        return TRANSITIONS.get(status, [])

    @staticmethod
    def get_label(status: str) -> str:
        """获取状态中文名"""
        return STATE_LABELS.get(status, status)

    @staticmethod
    def is_terminal(status: str) -> bool:
        """判断是否为终态"""
        return len(TRANSITIONS.get(status, [])) == 0

    @staticmethod
    def transition(from_status: str, to_status: str) -> str:
        """执行状态转换，返回新状态。如果转换不合法则抛出异常。"""
        if not StateMachine.can_transition(from_status, to_status):
            raise ValueError(
                f"无效的状态转换: {StateMachine.get_label(from_status)} → {StateMachine.get_label(to_status)}"
            )
        return to_status

    @staticmethod
    def get_all_states() -> list[dict]:
        """获取所有状态列表 (用于前端)"""
        return [
            {
                "value": s,
                "label": STATE_LABELS.get(s, s),
                "color": STATE_COLORS.get(s, "default"),
                "is_terminal": StateMachine.is_terminal(s),
                "next_states": TRANSITIONS.get(s, []),
            }
            for s in STATES
        ]
