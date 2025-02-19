import os; os.environ['no_proxy'] = '*' # 避免代理网络产生意外污染

def main():
    import gradio as gr
    if gr.__version__ not in ['3.28.3','3.32.2']: assert False, "需要特殊依赖，请务必用 pip install -r requirements.txt 指令安装依赖，详情信息见requirements.txt"
    from request_llm.bridge_all import predict
    from toolbox import format_io, find_free_port, on_file_uploaded, on_report_generated, get_conf, ArgsGeneralWrapper, load_chat_cookies, DummyWith
    # 建议您复制一个config_private.py放自己的秘密, 如API和代理网址, 避免不小心传github被别人看到
    proxies, WEB_PORT, LLM_MODEL, CONCURRENT_COUNT, AUTHENTICATION = get_conf('proxies', 'WEB_PORT', 'LLM_MODEL', 'CONCURRENT_COUNT', 'AUTHENTICATION')
    CHATBOT_HEIGHT, LAYOUT, AVAIL_LLM_MODELS, AUTO_CLEAR_TXT = get_conf('CHATBOT_HEIGHT', 'LAYOUT', 'AVAIL_LLM_MODELS', 'AUTO_CLEAR_TXT')
    ENABLE_AUDIO, AUTO_CLEAR_TXT = get_conf('ENABLE_AUDIO', 'AUTO_CLEAR_TXT')

    # 如果WEB_PORT是-1, 则随机选取WEB端口
    PORT = find_free_port() if WEB_PORT <= 0 else WEB_PORT
    from check_proxy import get_current_version
    from themes.theme import adjust_theme, advanced_css, theme_declaration
    initial_prompt = "Serve me as a writing and programming assistant."
    title_html = f"<h1 align=\"center\">GPT 学术优化 {get_current_version()}</h1>{theme_declaration}"
    description =  "代码开源和更新[地址🚀](https://github.com/binary-husky/gpt_academic)，"
    description += "感谢热情的[开发者们❤️](https://github.com/binary-husky/gpt_academic/graphs/contributors)"

    # 问询记录, python 版本建议3.9+（越新越好）
    import logging, uuid
    os.makedirs("gpt_log", exist_ok=True)
    try:logging.basicConfig(filename="gpt_log/chat_secrets.log", level=logging.INFO, encoding="utf-8", format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    except:logging.basicConfig(filename="gpt_log/chat_secrets.log", level=logging.INFO,  format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    # Disable logging output from the 'httpx' logger
    logging.getLogger("httpx").setLevel(logging.WARNING)
    print("所有问询记录将自动保存在本地目录./gpt_log/chat_secrets.log, 请注意自我隐私保护哦！")

    # 一些普通功能模块
    from core_functional import get_core_functions
    functional = get_core_functions()

    # 高级函数插件
    from crazy_functional import get_crazy_functions
    DEFAULT_FN_GROUPS, = get_conf('DEFAULT_FN_GROUPS')
    plugins = get_crazy_functions()
    all_plugin_groups = list(set([g for _, plugin in plugins.items() for g in plugin['Group'].split('|')]))
    match_group = lambda tags, groups: any([g in groups for g in tags.split('|')])

    # 处理markdown文本格式的转变
    gr.Chatbot.postprocess = format_io

    # 做一些外观色彩上的调整
    set_theme = adjust_theme()

    # 代理与自动更新
    from check_proxy import check_proxy, auto_update, warm_up_modules
    proxy_info = check_proxy(proxies)

    gr_L1 = lambda: gr.Row().style()
    gr_L2 = lambda scale, elem_id: gr.Column(scale=scale, elem_id=elem_id)
    if LAYOUT == "TOP-DOWN":
        gr_L1 = lambda: DummyWith()
        gr_L2 = lambda scale, elem_id: gr.Row()
        CHATBOT_HEIGHT /= 2

    cancel_handles = []
    with gr.Blocks(title="GPT 学术优化", theme=set_theme, analytics_enabled=False, css=advanced_css) as demo:
        gr.HTML(title_html)
        cookies = gr.State(load_chat_cookies())
        with gr_L1():
            with gr_L2(scale=2, elem_id="gpt-chat"):
                chatbot = gr.Chatbot(label=f"当前模型：{LLM_MODEL}", elem_id="gpt-chatbot")
                if LAYOUT == "TOP-DOWN":  chatbot.style(height=CHATBOT_HEIGHT)
                history = gr.State([])
            with gr_L2(scale=1, elem_id="gpt-panel"):
                with gr.Accordion("输入区", open=True, elem_id="input-panel") as area_input_primary:
                    with gr.Row():
                        txt = gr.Textbox(show_label=False, placeholder="Input question here.").style(container=False)
                    with gr.Row():
                        submitBtn = gr.Button("提交", variant="primary")
                    with gr.Row():
                        resetBtn = gr.Button("重置", variant="secondary"); resetBtn.style(size="sm")
                        stopBtn = gr.Button("停止", variant="secondary"); stopBtn.style(size="sm")
                        clearBtn = gr.Button("清除", variant="secondary", visible=False); clearBtn.style(size="sm")
                    if ENABLE_AUDIO: 
                        with gr.Row():
                            audio_mic = gr.Audio(source="microphone", type="numpy", streaming=True, show_label=False).style(container=False)
                    with gr.Row():
                        status = gr.Markdown(f"Tip: 按Enter提交, 按Shift+Enter换行。当前模型: {LLM_MODEL} \n {proxy_info}", elem_id="state-panel")
                with gr.Accordion("基础功能区", open=True, elem_id="basic-panel") as area_basic_fn:
                    with gr.Row():
                        for k in functional:
                            if ("Visible" in functional[k]) and (not functional[k]["Visible"]): continue
                            variant = functional[k]["Color"] if "Color" in functional[k] else "secondary"
                            functional[k]["Button"] = gr.Button(k, variant=variant)
                            functional[k]["Button"].style(size="sm")
                with gr.Accordion("函数插件区", open=True, elem_id="plugin-panel") as area_crazy_fn:
                    with gr.Row():
                        gr.Markdown("插件可读取“输入区”文本/路径作为参数（上传文件自动修正路径）")
                    with gr.Row(elem_id="input-plugin-group"):
                        plugin_group_sel = gr.Dropdown(choices=all_plugin_groups, label='', show_label=False, value=DEFAULT_FN_GROUPS, 
                                                      multiselect=True, interactive=True, elem_classes='normal_mut_select').style(container=False)
                    with gr.Row():
                        for k, plugin in plugins.items():
                            if not plugin.get("AsButton", True): continue
                            visible = True if match_group(plugin['Group'], DEFAULT_FN_GROUPS) else False
                            variant = plugins[k]["Color"] if "Color" in plugin else "secondary"
                            plugin['Button'] = plugins[k]['Button'] = gr.Button(k, variant=variant, visible=visible).style(size="sm")
                    with gr.Row():
                        with gr.Accordion("更多函数插件", open=True):
                            dropdown_fn_list = []
                            for k, plugin in plugins.items():
                                if not match_group(plugin['Group'], DEFAULT_FN_GROUPS): continue
                                if not plugin.get("AsButton", True): dropdown_fn_list.append(k)     # 排除已经是按钮的插件
                                elif plugin.get('AdvancedArgs', False): dropdown_fn_list.append(k)  # 对于需要高级参数的插件，亦在下拉菜单中显示
                            with gr.Row():
                                dropdown = gr.Dropdown(dropdown_fn_list, value=r"打开插件列表", label="", show_label=False).style(container=False)
                            with gr.Row():
                                plugin_advanced_arg = gr.Textbox(show_label=True, label="高级参数输入区", visible=False, 
                                                                 placeholder="这里是特殊函数插件的高级参数输入区").style(container=False)
                            with gr.Row():
                                switchy_bt = gr.Button(r"请先从插件列表中选择", variant="secondary").style(size="sm")
                    with gr.Row():
                        with gr.Accordion("点击展开“文件上传区”。上传本地文件/压缩包供函数插件调用。", open=False) as area_file_up:
                            file_upload = gr.Files(label="任何文件, 但推荐上传压缩文件(zip, tar)", file_count="multiple")
                with gr.Accordion("更换模型 & SysPrompt & 交互界面布局", open=(LAYOUT == "TOP-DOWN"), elem_id="interact-panel"):
                    system_prompt = gr.Textbox(show_label=True, placeholder=f"System Prompt", label="System prompt", value=initial_prompt)
                    top_p = gr.Slider(minimum=-0, maximum=1.0, value=1.0, step=0.01,interactive=True, label="Top-p (nucleus sampling)",)
                    temperature = gr.Slider(minimum=-0, maximum=2.0, value=1.0, step=0.01, interactive=True, label="Temperature",)
                    max_length_sl = gr.Slider(minimum=256, maximum=8192, value=4096, step=1, interactive=True, label="Local LLM MaxLength",)
                    checkboxes = gr.CheckboxGroup(["基础功能区", "函数插件区", "底部输入区", "输入清除键", "插件参数区"], value=["基础功能区", "函数插件区"], label="显示/隐藏功能区")
                    md_dropdown = gr.Dropdown(AVAIL_LLM_MODELS, value=LLM_MODEL, label="更换LLM模型/请求源").style(container=False)
                    gr.Markdown(description)
                with gr.Accordion("备选输入区", open=True, visible=False, elem_id="input-panel2") as area_input_secondary:
                    with gr.Row():
                        txt2 = gr.Textbox(show_label=False, placeholder="Input question here.", label="输入区2").style(container=False)
                    with gr.Row():
                        submitBtn2 = gr.Button("提交", variant="primary")
                    with gr.Row():
                        resetBtn2 = gr.Button("重置", variant="secondary"); resetBtn2.style(size="sm")
                        stopBtn2 = gr.Button("停止", variant="secondary"); stopBtn2.style(size="sm")
                        clearBtn2 = gr.Button("清除", variant="secondary", visible=False); clearBtn2.style(size="sm")

        # 功能区显示开关与功能区的互动
        def fn_area_visibility(a):
            ret = {}
            ret.update({area_basic_fn: gr.update(visible=("基础功能区" in a))})
            ret.update({area_crazy_fn: gr.update(visible=("函数插件区" in a))})
            ret.update({area_input_primary: gr.update(visible=("底部输入区" not in a))})
            ret.update({area_input_secondary: gr.update(visible=("底部输入区" in a))})
            ret.update({clearBtn: gr.update(visible=("输入清除键" in a))})
            ret.update({clearBtn2: gr.update(visible=("输入清除键" in a))})
            ret.update({plugin_advanced_arg: gr.update(visible=("插件参数区" in a))})
            if "底部输入区" in a: ret.update({txt: gr.update(value="")})
            return ret
        checkboxes.select(fn_area_visibility, [checkboxes], [area_basic_fn, area_crazy_fn, area_input_primary, area_input_secondary, txt, txt2, clearBtn, clearBtn2, plugin_advanced_arg] )
        # 整理反复出现的控件句柄组合
        input_combo = [cookies, max_length_sl, md_dropdown, txt, txt2, top_p, temperature, chatbot, history, system_prompt, plugin_advanced_arg]
        output_combo = [cookies, chatbot, history, status]
        predict_args = dict(fn=ArgsGeneralWrapper(predict), inputs=input_combo, outputs=output_combo)
        # 提交按钮、重置按钮
        cancel_handles.append(txt.submit(**predict_args))
        cancel_handles.append(txt2.submit(**predict_args))
        cancel_handles.append(submitBtn.click(**predict_args))
        cancel_handles.append(submitBtn2.click(**predict_args))
        resetBtn.click(lambda: ([], [], "已重置"), None, [chatbot, history, status])
        resetBtn2.click(lambda: ([], [], "已重置"), None, [chatbot, history, status])
        clearBtn.click(lambda: ("",""), None, [txt, txt2])
        clearBtn2.click(lambda: ("",""), None, [txt, txt2])
        if AUTO_CLEAR_TXT:
            submitBtn.click(lambda: ("",""), None, [txt, txt2])
            submitBtn2.click(lambda: ("",""), None, [txt, txt2])
            txt.submit(lambda: ("",""), None, [txt, txt2])
            txt2.submit(lambda: ("",""), None, [txt, txt2])
        # 基础功能区的回调函数注册
        for k in functional:
            if ("Visible" in functional[k]) and (not functional[k]["Visible"]): continue
            click_handle = functional[k]["Button"].click(fn=ArgsGeneralWrapper(predict), inputs=[*input_combo, gr.State(True), gr.State(k)], outputs=output_combo)
            cancel_handles.append(click_handle)
        # 文件上传区，接收文件后与chatbot的互动
        file_upload.upload(on_file_uploaded, [file_upload, chatbot, txt, txt2, checkboxes, cookies], [chatbot, txt, txt2, cookies])
        # 函数插件-固定按钮区
        for k in plugins:
            if not plugins[k].get("AsButton", True): continue
            click_handle = plugins[k]["Button"].click(ArgsGeneralWrapper(plugins[k]["Function"]), [*input_combo, gr.State(PORT)], output_combo)
            click_handle.then(on_report_generated, [cookies, file_upload, chatbot], [cookies, file_upload, chatbot])
            cancel_handles.append(click_handle)
        # 函数插件-下拉菜单与随变按钮的互动
        def on_dropdown_changed(k):
            variant = plugins[k]["Color"] if "Color" in plugins[k] else "secondary"
            ret = {switchy_bt: gr.update(value=k, variant=variant)}
            if plugins[k].get("AdvancedArgs", False): # 是否唤起高级插件参数区
                ret.update({plugin_advanced_arg: gr.update(visible=True,  label=f"插件[{k}]的高级参数说明：" + plugins[k].get("ArgsReminder", [f"没有提供高级参数功能说明"]))})
            else:
                ret.update({plugin_advanced_arg: gr.update(visible=False, label=f"插件[{k}]不需要高级参数。")})
            return ret
        dropdown.select(on_dropdown_changed, [dropdown], [switchy_bt, plugin_advanced_arg] )
        def on_md_dropdown_changed(k):
            return {chatbot: gr.update(label="当前模型："+k)}
        md_dropdown.select(on_md_dropdown_changed, [md_dropdown], [chatbot] )
        # 随变按钮的回调函数注册
        def route(request: gr.Request, k, *args, **kwargs):
            if k in [r"打开插件列表", r"请先从插件列表中选择"]: return
            yield from ArgsGeneralWrapper(plugins[k]["Function"])(request, *args, **kwargs)
        click_handle = switchy_bt.click(route,[switchy_bt, *input_combo, gr.State(PORT)], output_combo)
        click_handle.then(on_report_generated, [cookies, file_upload, chatbot], [cookies, file_upload, chatbot])
        cancel_handles.append(click_handle)
        # 终止按钮的回调函数注册
        stopBtn.click(fn=None, inputs=None, outputs=None, cancels=cancel_handles)
        stopBtn2.click(fn=None, inputs=None, outputs=None, cancels=cancel_handles)
        plugins_as_btn = {name:plugin for name, plugin in plugins.items() if plugin.get('Button', None)}
        def on_group_change(group_list):
            btn_list = []
            fns_list = []
            if not group_list: # 处理特殊情况：没有选择任何插件组
                return [*[plugin['Button'].update(visible=False) for _, plugin in plugins_as_btn.items()], gr.Dropdown.update(choices=[])]
            for k, plugin in plugins.items():
                if plugin.get("AsButton", True): 
                    btn_list.append(plugin['Button'].update(visible=match_group(plugin['Group'], group_list))) # 刷新按钮
                    if plugin.get('AdvancedArgs', False): dropdown_fn_list.append(k) # 对于需要高级参数的插件，亦在下拉菜单中显示
                elif match_group(plugin['Group'], group_list): fns_list.append(k) # 刷新下拉列表
            return [*btn_list, gr.Dropdown.update(choices=fns_list)]
        plugin_group_sel.select(fn=on_group_change, inputs=[plugin_group_sel], outputs=[*[plugin['Button'] for name, plugin in plugins_as_btn.items()], dropdown])
        if ENABLE_AUDIO: 
            from crazy_functions.live_audio.audio_io import RealtimeAudioDistribution
            rad = RealtimeAudioDistribution()
            def deal_audio(audio, cookies):
                rad.feed(cookies['uuid'].hex, audio)
            audio_mic.stream(deal_audio, inputs=[audio_mic, cookies])

        def init_cookie(cookies, chatbot):
            # 为每一位访问的用户赋予一个独一无二的uuid编码
            cookies.update({'uuid': uuid.uuid4()})
            return cookies
        demo.load(init_cookie, inputs=[cookies, chatbot], outputs=[cookies])
        demo.load(lambda: 0, inputs=None, outputs=None, _js='()=>{ChatBotHeight();}')
        
    # gradio的inbrowser触发不太稳定，回滚代码到原始的浏览器打开函数
    def auto_opentab_delay():
        import threading, webbrowser, time
        print(f"如果浏览器没有自动打开，请复制并转到以下URL：")
        print(f"\t（亮色主题）: http://localhost:{PORT}")
        print(f"\t（暗色主题）: http://localhost:{PORT}/?__theme=dark")
        def open():
            time.sleep(2)       # 打开浏览器
            DARK_MODE, = get_conf('DARK_MODE')
            if DARK_MODE: webbrowser.open_new_tab(f"http://localhost:{PORT}/?__theme=dark")
            else: webbrowser.open_new_tab(f"http://localhost:{PORT}")
        threading.Thread(target=open, name="open-browser", daemon=True).start()
        threading.Thread(target=auto_update, name="self-upgrade", daemon=True).start()
        threading.Thread(target=warm_up_modules, name="warm-up", daemon=True).start()

    auto_opentab_delay()
    demo.queue(concurrency_count=CONCURRENT_COUNT).launch(
        server_name="0.0.0.0", 
        server_port=PORT,
        favicon_path="docs/logo.png", 
        auth=AUTHENTICATION if len(AUTHENTICATION) != 0 else None,
        blocked_paths=["config.py","config_private.py","docker-compose.yml","Dockerfile"])

    # 如果需要在二级路径下运行
    # CUSTOM_PATH, = get_conf('CUSTOM_PATH')
    # if CUSTOM_PATH != "/": 
    #     from toolbox import run_gradio_in_subpath
    #     run_gradio_in_subpath(demo, auth=AUTHENTICATION, port=PORT, custom_path=CUSTOM_PATH)
    # else: 
    #     demo.launch(server_name="0.0.0.0", server_port=PORT, auth=AUTHENTICATION, favicon_path="docs/logo.png",
    #                 blocked_paths=["config.py","config_private.py","docker-compose.yml","Dockerfile"])

if __name__ == "__main__":
    main()
