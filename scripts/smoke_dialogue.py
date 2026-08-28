"""
对话冒烟/演示脚本
用法：
    uv run python scripts/smoke_dialogue.py            # 跑全部五场景 + 闲聊/SSE
    uv run python scripts/smoke_dialogue.py --step     # 单步模式：input("<sid>你说: ")
"""

import argparse
import json
import sys

import httpx

BASE = "http://127.0.0.1:18082"
DEMO_USER_ID = "331"  # smoke 数据里订单/报名都比较全的演示学员


def new_session(client: httpx.Client, user_id: str = DEMO_USER_ID) -> str:
    response = client.post(f"{BASE}/api/sessions", json={"user_id": user_id})
    session_id = response.json()["session_id"]
    print(f"[会话] {session_id}（学员 user_id={user_id}）")
    return session_id


def show(resp_json: dict):
    for message in resp_json.get("messages", []):
        prefix = "[BOT]" + ("[卡片]" if message.get("object") else "")
        print(f"{prefix} {message['text']}")
    state = resp_json.get("session_state") or {}
    active_task = state.get("active_task")
    if active_task:
        slots = {
            k: (v[:40] + "…" if isinstance(v, str) and len(v) > 40 else v)
            for k, v in active_task["slots"].items()
        }
        print(
            f"[状态] 流程={active_task['flow_id']} 步骤={active_task['step_id']} 槽位={slots}"
        )
    if state.get("paused_tasks"):
        print(f"[状态] 暂停栈={[t['flow_id'] for t in state['paused_tasks']]}")


def say(client: httpx.Client, sid: str, text: str, user_id: str = DEMO_USER_ID) -> dict:
    print(f"\n[学员] {text}")
    response = client.post(
        f"{BASE}/api/chat",
        json={"sender_id": sid, "user_id": user_id, "text": text},
        timeout=180,
    )
    resp_json = response.json()
    show(resp_json)
    return resp_json


def send_object(client: httpx.Client, sid: str, object_payload: dict) -> dict:
    print(
        f"\n[学员][发送卡片] type={object_payload['type']} title={object_payload['title']}"
    )
    response = client.post(
        f"{BASE}/api/chat",
        json={"sender_id": sid, "object": object_payload},
        timeout=180,
    )
    resp_json = response.json()
    show(resp_json)
    return resp_json


def stream_say(client: httpx.Client, sid: str, text: str, user_id: str = DEMO_USER_ID):
    print(f"\n[学员](SSE) {text}")
    collected = ""
    with client.stream(
        "POST",
        f"{BASE}/api/chat/stream",
        json={"sender_id": sid, "user_id": user_id, "text": text},
        timeout=180,
    ) as response:
        event = None
        for line in response.iter_lines():
            if not line:
                continue
            if line.startswith("event: "):
                event = line[len("event: ") :]
                continue
            if line.startswith("data: ") and event:
                data = json.loads(line[len("data: ") :])
                if event == "meta":
                    print("[SSE meta]")
                elif event == "delta":
                    collected += data["text"]
                    print(data["text"], end="", flush=True)
                elif event == "object":
                    print(f"\n[SSE 卡片] {data['object']}")
                elif event == "done":
                    state = data.get("session_state") or {}
                    task = state.get("active_task")
                    print(f"\n[SSE done] 状态流程={task and task['flow_id']}")
                elif event == "error":
                    print(f"\n[SSE error] {data}")


def scenario_course(client: httpx.Client, sid: str):
    print("\n========== 场景1：课程咨询 ==========")
    say(client, sid, "我想了解一下全栈开发方面的课程")
    say(client, sid, "全栈开发系统班")


def scenario_order(client: httpx.Client, sid: str):
    print("\n========== 场景2：订单查询 ==========")
    say(client, sid, "帮我查下订单 ORD0000000672")


def scenario_progress(client: httpx.Client, sid: str):
    print("\n========== 场景3：学习进度查询 ==========")
    say(client, sid, "我在全栈开发系统班的学习进度怎么样？")


def scenario_refund(client: httpx.Client, sid: str):
    print("\n========== 场景4：退费申请（多轮槽位收集）==========")
    say(client, sid, "我要退费")
    say(client, sid, "ORD0000000672")
    say(client, sid, "课程太难了跟不上")
    say(client, sid, "课程不满意")


def scenario_ticket(client: httpx.Client, sid: str):
    print("\n========== 场景5：工单提交 ==========")
    say(client, sid, "第三章的视频一直加载不出来，我要投诉")
    say(client, sid, "ORD0000000738")
    say(client, sid, "第三章的视频一直转圈加载不出来，反复重试也不行")


def scenario_control(client: httpx.Client, sid: str):
    print("\n========== 场景6：任务中断/恢复/取消 + 对象消息 + 闲聊 + 澄清 ==========")
    say(client, sid, "我要退款")  # 开启退费流程 → 追问订单号
    say(client, sid, "帮我查一下订单状态")  # 中断退费，切到订单查询 → 应提示先暂存
    say(client, sid, "继续刚才的退费")  # resume_flow
    say(client, sid, "取消")  # cancel 当前流程
    send_object(
        client,
        sid,
        {
            "id": "ORD0000000672",
            "type": "order",
            "title": "订单 ORD0000000672",
            "attributes": {"amount": 4999},
        },
    )
    say(client, sid, "今天天气真不错啊")  # 闲聊兜底
    say(client, sid, "你氪什么金啊咯咯哒呵呵")  # 澄清


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        default="all",
        help="all|course|order|progress|refund|ticket|control|stream",
    )
    args = parser.parse_args()

    with httpx.Client() as client:
        health = client.get(f"{BASE}/health").json()
        assert health == {"status": "ok"}, health

        scenarios = {
            "course": lambda sid: scenario_course(client, sid),
            "order": lambda sid: scenario_order(client, sid),
            "progress": lambda sid: scenario_progress(client, sid),
            "refund": lambda sid: scenario_refund(client, sid),
            "ticket": lambda sid: scenario_ticket(client, sid),
            "control": lambda sid: scenario_control(client, sid),
            "stream": lambda sid: stream_say(
                client, sid, "查一下我的订单 ORD0000000172"
            ),
        }

        if args.scenario != "all":
            sid = new_session(client)
            scenarios[args.scenario](sid)
        else:
            for name, runner in scenarios.items():
                sid = new_session(client)
                try:
                    runner(sid)
                except Exception as error:
                    print(f"[{name}] 场景失败: {error}", file=sys.stderr)


if __name__ == "__main__":
    main()
