#!/usr/bin/env python3
"""웹 데모 (Gradio)
카톡 txt 업로드 → Qwen3.8이 말투(style.md) + 기억(memory.md) 추출 → 남자친구와 채팅
메시지마다 Qwen3.8이 🚨비상상황 / ❓주인 확인 필요 여부를 판단해 '주인 패널'에 알려줍니다.

실행: python app.py  →  http://localhost:7860
"""
import datetime
import os

import gradio as gr

from boyfriend import analyze, config, default_out_dir, has_saved, load_boyfriend, load_kakao, speakers
from boyfriend import llm

CSS = """
.alert-box {background:#fde8e8; border:2px solid #e02424; border-radius:10px; padding:10px 14px;}
.ask-box {background:#fff8e1; border:2px solid #f5a623; border-radius:10px; padding:10px 14px;}
"""


def read(out, name):
    return open(os.path.join(out, name), encoding="utf-8").read()


def saved_session(path, me):
    """이 대화 파일 + 내 이름 기준의 저장된 분석 폴더 (없으면 None)"""
    if not path or not me:
        return None
    out = default_out_dir(path, me)
    return out if has_saved(out) else None


def load_btn_update(loaded, me):
    """선택한 이름 기준 저장 분석이 있을 때만 불러오기 버튼 표시"""
    out = saved_session(loaded[0], me) if loaded else None
    if not out:
        return gr.update(visible=False)
    t = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(out, "memory.md")))
    return gr.update(visible=True, value=f"💾 저장된 '{me}' 분석 불러오기 ({t:%m/%d %H:%M}, 바로 대화)")


def on_upload(file, limit):
    if not file:
        return gr.update(choices=[], value=None), None, "파일을 올려주세요.", gr.update(visible=False)
    path = file if isinstance(file, str) else file.name
    msgs = load_kakao(path, int(limit))
    names = speakers(msgs)
    if not msgs:
        return gr.update(choices=[], value=None), None, "메시지를 찾지 못했습니다.", gr.update(visible=False)
    saved_names = [n for n in names if saved_session(path, n)]
    info = (f"앞 **{len(msgs)}개** 메시지 ({msgs[0].time} ~ {msgs[-1].time})  \n"
            f"말투 분석: 최근 {min(config.STYLE_MESSAGES, len(msgs))}개 · 기억: 전체 {len(msgs)}개  \n"
            f"참여자: {', '.join(names)}  \n⚠️ 아래에서 **내 이름**을 꼭 확인하세요.")
    if saved_names:
        info += f"  \n💾 저장된 분석: **{', '.join(saved_names)}** 기준"
    value = saved_names[0] if saved_names else names[0]
    loaded = (path, msgs)
    return gr.update(choices=names, value=value), loaded, info, load_btn_update(loaded, value)


def _ready(out, bf, msg):
    hello = [{"role": "assistant", "content": f"({msg} {bf.partner} 입장에서 말 걸어보세요)"}]
    return out, bf, read(out, "style.md"), read(out, "memory.md"), hello, *panel(bf)


def on_analyze(loaded, me, think, progress=gr.Progress()):
    if not loaded or not me:
        raise gr.Error("대화 파일을 올리고 내 이름을 선택하세요.")
    path, msgs = loaded
    progress(0.1, desc="Qwen3.8이 말투와 기억을 분석 중... (1~2분)")
    out = analyze(msgs, me, default_out_dir(path, me), think=think)
    bf = load_boyfriend(out)
    return _ready(out, bf, f"{bf.me} 말투 + 기억 장착 완료!")


def on_load_saved(loaded, me):
    """선택한 이름 기준으로 저장된 style.md / memory.md를 불러와 분석 없이 바로 대화"""
    if not loaded:
        raise gr.Error("대화 파일을 먼저 올려주세요.")
    out = saved_session(loaded[0], me)
    if not out:
        raise gr.Error(f"'{me}' 기준 저장된 분석이 없어요. '말투 + 기억 분석'을 눌러주세요.")
    bf = load_boyfriend(out)
    return _ready(out, bf, f"저장된 {bf.me} 말투 + 기억을 불러왔어요!")


def on_apply(out, style_md, memory_md):
    """화면에서 고친 style.md / memory.md를 저장하고 다시 적용"""
    if not out:
        raise gr.Error("먼저 분석을 실행하세요.")
    for name, text in (("style.md", style_md), ("memory.md", memory_md)):
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            f.write(text)
    gr.Info("수정한 말투/기억을 적용했어요. 대화가 초기화됩니다.")
    bf = load_boyfriend(out)
    return bf, [], *panel(bf)


def panel(bf):
    """주인 패널: (비상 알림 md, 확인 질문 md, 답변 입력창 표시 여부)"""
    if not bf:
        return "", "", gr.update(visible=False)
    alerts = ""
    if bf.alerts:
        rows = "\n".join(f"- **[{a['severity'] or '?'}]** {a['time'][11:16]} \"{a['message']}\" — {a['reason']}"
                         for a in reversed(bf.alerts[-5:]))
        alerts = f"<div class='alert-box'>\n\n### 🚨 비상 알림 ({len(bf.alerts)}건)\n{rows}\n\n</div>"
    ask = ""
    if bf.pending:
        ask = (f"<div class='ask-box'>\n\n### ❓ 확인이 필요해요\n**{bf.partner}:** \"{bf.pending['partner_message']}\"  \n"
               f"{bf.pending['question']}\n\n</div>")
    return alerts, ask, gr.update(visible=bool(bf.pending))


def on_chat(text, history, bf):
    if not bf:
        raise gr.Error("먼저 '분석'을 눌러주세요.")
    if not text.strip():
        yield history, "", *panel(bf)
        return
    history = history + [{"role": "user", "content": text},
                         {"role": "assistant", "content": "…"}]
    yield history, "", *panel(bf)
    res = bf.check(text)  # 1) Qwen3.8 판단
    if res.emergency:
        gr.Warning(f"🚨 비상상황 감지: {res.emergency_reason}")
    if bf.pending:
        gr.Info("❓ 주인 확인이 필요한 질문이에요. 오른쪽 아래에서 답해주세요.")
    reply = ""
    for reply in bf.reply_stream(text, res):  # 2) 판단에 맞춘 답장
        yield history[:-1] + [{"role": "assistant", "content": reply}], "", *panel(bf)
    yield history[:-1] + [{"role": "assistant", "content": l} for l in reply.splitlines() if l], "", *panel(bf)


def on_owner_answer(answer, history, bf, out):
    if not bf or not bf.pending:
        raise gr.Error("확인 대기 중인 질문이 없습니다.")
    if not answer.strip():
        raise gr.Error("답변을 입력하세요.")
    reply = ""
    for reply in bf.answer_owner_stream(answer):  # 3) 주인 답변 → 내 말투로 전달 + memory.md 저장
        yield history + [{"role": "assistant", "content": reply}], "", *panel(bf), gr.update()
    final = history + [{"role": "assistant", "content": l} for l in reply.splitlines() if l]
    yield final, "", *panel(bf), read(out, "memory.md") if out else gr.update()


def on_skip(bf):
    if bf:
        bf.pending = None
    return panel(bf)


def on_reset(bf):
    if bf:
        bf.reset()
    return [], *panel(bf)


with gr.Blocks(title="내 말투 남자친구") as demo:
    gr.Markdown("# 💬 내 말투 남자친구\n카톡 대화를 올리면 **Qwen3.8**이 내 **말투**와 우리의 **기억**을 배워서 남자친구처럼 대답해요. "
                "급한 상황이나 모르는 질문은 **나(주인)에게 알려줘요.**")
    loaded_state, out_state, bf_state = gr.State(), gr.State(), gr.State()
    with gr.Row():
        with gr.Column(scale=1):
            file = gr.File(label="1. 대화 파일 (카카오톡 txt / JSON)", file_types=[".txt", ".json"])
            limit = gr.Slider(100, 3000, value=config.MAX_MESSAGES, step=100, label="앞에서부터 사용할 메시지 수")
            info = gr.Markdown()
            me = gr.Dropdown(label="2. 대화 속 내 이름", choices=[])
            think = gr.Checkbox(label="말투 정밀 분석 (Qwen thinking 모드, 느림)", value=False)
            load_btn = gr.Button("💾 저장된 분석 불러오기 (바로 대화)", variant="primary", visible=False)
            analyze_btn = gr.Button("3. 말투 + 기억 분석 (새로 분석, 1~2분)", variant="secondary")
            with gr.Tabs():
                with gr.Tab("🗣️ style.md (말투)"):
                    style_box = gr.Textbox(lines=16, max_lines=30, show_label=False)
                with gr.Tab("🧠 memory.md (기억)"):
                    memory_box = gr.Textbox(lines=16, max_lines=30, show_label=False)
            apply_btn = gr.Button("수정한 말투/기억 적용")
        with gr.Column(scale=1):
            chatbot = gr.Chatbot(label="남자친구 (상대방 화면)", height=480)
            box = gr.Textbox(placeholder="상대방 입장에서 메시지 입력 후 Enter", show_label=False)
            reset_btn = gr.Button("대화 초기화", size="sm")
            gr.Markdown("### 👤 주인 패널")
            alert_md = gr.Markdown()
            ask_md = gr.Markdown()
            with gr.Group(visible=False) as answer_group:
                owner_box = gr.Textbox(placeholder="내가 직접 답하기 → 내 말투로 바꿔 전달하고 기억에 저장", show_label=False)
                with gr.Row():
                    owner_btn = gr.Button("답변 보내기", variant="primary")
                    skip_btn = gr.Button("나중에")
    gr.Markdown(f"<sub>Model: `{config.VLLM_MODEL}` @ `{config.VLLM_BASE_URL}`</sub>")

    panel_out = [alert_md, ask_md, answer_group]
    ready_out = [out_state, bf_state, style_box, memory_box, chatbot, *panel_out]
    file.change(on_upload, [file, limit], [me, loaded_state, info, load_btn])
    limit.release(on_upload, [file, limit], [me, loaded_state, info, load_btn])
    me.change(load_btn_update, [loaded_state, me], load_btn)
    load_btn.click(on_load_saved, [loaded_state, me], ready_out)
    analyze_btn.click(on_analyze, [loaded_state, me, think], ready_out).then(
        load_btn_update, [loaded_state, me], load_btn)
    apply_btn.click(on_apply, [out_state, style_box, memory_box], [bf_state, chatbot, *panel_out])
    box.submit(on_chat, [box, chatbot, bf_state], [chatbot, box, *panel_out])
    owner_btn.click(on_owner_answer, [owner_box, chatbot, bf_state, out_state],
                    [chatbot, owner_box, *panel_out, memory_box])
    owner_box.submit(on_owner_answer, [owner_box, chatbot, bf_state, out_state],
                     [chatbot, owner_box, *panel_out, memory_box])
    skip_btn.click(on_skip, bf_state, panel_out)
    reset_btn.click(on_reset, bf_state, [chatbot, *panel_out])

if __name__ == "__main__":
    try:
        print("vLLM 연결:", llm.health())
    except Exception as e:
        print("⚠️ vLLM 연결 실패:", e)
    demo.queue().launch(server_name="0.0.0.0", server_port=7860, css=CSS)
