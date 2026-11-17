状态S=(可训练参数,optimizer,scaler,RNG,模式)。每动作恢复同一前缀，执行d=1/2次[7 Calendar+1 replay]实际更新。保存完整可恢复状态并严格hash往返后，测dev与check；测量后恢复该状态。
V_k(d)=[L_dev(background_d)-L_dev(action_k_d)]/实际replay输入token；只以dev选择argmax，check仅验证。四技能宏平均包含跨技能损害，另输出矩阵。
本轮验证短程响应代理，不把NLL收益等同严格Joint，也不声称在线自适应已成功。
