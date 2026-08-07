"""测试状态机"""

import pytest
from app.utils.state_machine import StateMachine, STATES, TRANSITIONS, STATE_LABELS


class TestStateMachine:
    """求职状态机测试"""

    def test_can_transition_valid(self):
        """测试合法状态转换"""
        assert StateMachine.can_transition("applied", "waiting") is True
        assert StateMachine.can_transition("applied", "rejected") is True
        assert StateMachine.can_transition("resume_screening", "written_test") is True
        assert StateMachine.can_transition("resume_screening", "interview_1") is True
        assert StateMachine.can_transition("interview_1", "interview_2") is True
        assert StateMachine.can_transition("interview_2", "interview_3") is True
        assert StateMachine.can_transition("interview_3", "offer") is True
        assert StateMachine.can_transition("offer", "accepted") is True

    def test_can_transition_invalid(self):
        """测试非法状态转换"""
        assert StateMachine.can_transition("applied", "offer") is False
        assert StateMachine.can_transition("resume_screening", "offer") is False
        assert StateMachine.can_transition("accepted", "rejected") is False  # 终态不能转换
        assert StateMachine.can_transition("rejected", "applied") is False

    def test_can_transition_unknown_status(self):
        """测试未知状态"""
        assert StateMachine.can_transition("nonexistent", "applied") is False
        assert StateMachine.can_transition("applied", "nonexistent") is False

    def test_get_next_states(self):
        """测试获取下一个合法状态"""
        next_states = StateMachine.get_next_states("applied")
        assert "waiting" in next_states
        assert "rejected" in next_states
        assert "withdrawn" in next_states

    def test_get_next_states_terminal(self):
        """终态无下一个状态"""
        assert StateMachine.get_next_states("accepted") == []
        assert StateMachine.get_next_states("rejected") == []
        assert StateMachine.get_next_states("withdrawn") == []

    def test_get_label(self):
        """测试中文标签"""
        assert StateMachine.get_label("applied") == "已投递"
        assert StateMachine.get_label("interview_1") == "一面"
        assert StateMachine.get_label("offer") == "收到Offer"

    def test_get_label_unknown(self):
        """测试未知状态返回原始值"""
        assert StateMachine.get_label("unknown") == "unknown"

    def test_is_terminal(self):
        """测试终态判断"""
        assert StateMachine.is_terminal("accepted") is True
        assert StateMachine.is_terminal("rejected") is True
        assert StateMachine.is_terminal("withdrawn") is True
        assert StateMachine.is_terminal("applied") is False
        assert StateMachine.is_terminal("interview_1") is False

    def test_transition_valid(self):
        """测试执行合法状态转换"""
        result = StateMachine.transition("applied", "waiting")
        assert result == "waiting"

    def test_transition_invalid_raises(self):
        """测试非法状态转换抛出异常"""
        with pytest.raises(ValueError, match="无效的状态转换"):
            StateMachine.transition("applied", "offer")

    def test_get_all_states(self):
        """测试获取所有状态列表"""
        all_states = StateMachine.get_all_states()
        assert len(all_states) == len(STATES)
        for state in all_states:
            assert "value" in state
            assert "label" in state
            assert "color" in state
            assert "is_terminal" in state
            assert "next_states" in state


class TestStateDefinitions:
    """测试状态定义完整性"""

    def test_every_state_has_label(self):
        for state in STATES:
            assert state in STATE_LABELS, f"状态 {state} 缺少中文标签"

    def test_every_state_in_transitions(self):
        for state in STATES:
            assert state in TRANSITIONS, f"状态 {state} 不在转换映射中"

    def test_transitions_only_use_valid_states(self):
        for from_state, to_states in TRANSITIONS.items():
            assert from_state in STATES
            for to_state in to_states:
                assert to_state in STATES, f"目标状态 {to_state} 不在合法状态列表中"

    def test_terminal_states_have_no_transitions(self):
        """终态不能有出边"""
        for state in ["accepted", "rejected", "withdrawn"]:
            assert TRANSITIONS[state] == []
