        function showToast(message, type = 'info') {
            const container = document.getElementById('toastContainer');
            if (!container) return;
            const toast = document.createElement('div');
            toast.style.cssText = `
                padding: 12px 20px;
                border-radius: 10px;
                background: rgba(30, 41, 59, 0.9);
                backdrop-filter: blur(8px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                color: white;
                font-size: 14px;
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
                display: flex;
                align-items: center;
                gap: 10px;
                transform: translateX(110%);
                transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            `;
            
            let icon = '<i class="fas fa-info-circle" style="color: var(--primary);"></i>';
            if (type === 'success') {
                icon = '<i class="fas fa-check-circle" style="color: var(--success);"></i>';
                toast.style.borderLeft = '4px solid var(--success)';
            } else if (type === 'error') {
                icon = '<i class="fas fa-exclamation-circle" style="color: var(--danger);"></i>';
                toast.style.borderLeft = '4px solid var(--danger)';
            }

            toast.innerHTML = `${icon} <span>${message}</span>`;
            container.appendChild(toast);

            setTimeout(() => toast.style.transform = 'translateX(0)', 10);

            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(110%)';
                setTimeout(() => toast.remove(), 400);
            }, 3500);
        }
        let savedScrollPosition = 0;
        function lockBodyScroll() {
            // 防止重复锁定
            if (document.body.style.position === 'fixed') return;
            savedScrollPosition = window.pageYOffset || document.documentElement.scrollTop;
            document.body.style.position = 'fixed';
            document.body.style.top = `-${savedScrollPosition}px`;
            document.body.style.width = '100%';
        }
        function unlockBodyScroll() {
            if (document.body.style.position !== 'fixed') return;
            document.body.style.position = '';
            document.body.style.top = '';
            document.body.style.width = '';
            window.scrollTo(0, savedScrollPosition);
        }

        function openModal(id) {
            document.getElementById(id).classList.add('active');
            lockBodyScroll(); /* 真正的移动端背景防穿透 */
        }

        function showAlert(message, title = '提示') {
            document.getElementById('alertTitle').innerText = title;
            document.getElementById('alertMessage').innerText = message;
            openModal('alertModal');
        }

        function showConfirmModal(title, message, onConfirm) {
            const tEl = document.getElementById('confirmTitle');
            const mEl = document.getElementById('confirmMessage');
            if (tEl) tEl.innerText = title;
            if (mEl) mEl.innerText = message;

            const confirmBtn = document.getElementById('confirmBtn');
            if (confirmBtn) {
                const newConfirmBtn = confirmBtn.cloneNode(true);
                confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

                newConfirmBtn.onclick = () => {
                    onConfirm();
                    closeModal('confirmModal');
                };
            }
            openModal('confirmModal');
        }

        function showInputModal(title, label, defaultValue, onConfirm) {
            const tEl = document.getElementById('inputModalTitle');
            const lEl = document.getElementById('inputModalLabel');
            if (tEl) tEl.innerText = title;
            if (lEl) lEl.innerText = label;
            
            const field = document.getElementById('inputModalField');
            if (field) {
                field.value = defaultValue || '';
            }

            const confirmBtn = document.getElementById('inputModalConfirmBtn');
            if (confirmBtn) {
                const newConfirmBtn = confirmBtn.cloneNode(true);
                confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
                newConfirmBtn.onclick = () => {
                    const value = field.value.trim();
                    if (value) {
                        onConfirm(value);
                        closeModal('inputModal');
                    } else {
                        showToast('输入不能为空', 'error');
                    }
                };
            }
            openModal('inputModal');
            setTimeout(() => field && field.focus(), 100);
        }

        function editSchedule(scheduleId, targetTime, routeType, randomDelay) {
            document.getElementById('edit_sched_id').value = scheduleId;
            document.getElementById('edit_sched_time').value = targetTime;
            document.getElementById('edit_sched_route').value = routeType;
            document.getElementById('edit_sched_delay').value = randomDelay || 0;
            openModal('editScheduleModal');
        }
        function closeModal(id) {
            document.getElementById(id).classList.remove('active');
            /* 检查是否还有其他活动模态框，如果没有则恢复 body 滚动 */
            if (!document.querySelector('.modal-overlay.active')) {
                unlockBodyScroll();
            }
            // Reset validation messages
            if (id === 'addUserModal') document.getElementById('add_validation_msg').innerHTML = '';
            if (id === 'editUserModal') document.getElementById('edit_validation_msg').innerHTML = '';
            
            if (id === 'historyModal') {
                if (window._cloudPreviewModalMap) {
                    window._cloudPreviewModalMap.remove();
                    window._cloudPreviewModalMap = null;
                }
            } else if (id === 'localHistoryModal') {
                const btn = document.getElementById('exportLocalHistoryBtn');
                if (btn) btn.style.display = 'none';
                const clearBtn = document.getElementById('clearLocalHistoryBtn');
                if (clearBtn) clearBtn.style.display = 'none';
                window.currentLocalLogs = null;
                window.currentViewingUserId = null;
            }
        }

        async function clearSystemLogs() {
            showConfirmModal('确认清空日志', '确定要清空所有系统运行日志吗？此操作不可恢复。', async () => {
                try {
                    const res = await fetch('/api/logs/clear', {method: 'POST'});
                    const result = await res.json();
                    if(result.success) {
                        showToast('系统日志已清理完毕', 'success');
                        const contentEl = document.getElementById("logContent");
                        if (contentEl) contentEl.textContent = "系统运行日志已清空";
                        fetchLogs();
                    } else {
                        showToast('清理失败: ' + result.message, 'error');
                    }
                } catch (err) {
                    showToast('网络错误: ' + err.message, 'error');
                }
            });
        }

        async function clearLocalHistory() {
            if(!window.currentViewingUserId) return;
            showConfirmModal('确认清空日志', '确定要清空该账户的本地运行日志吗？此操作不可恢复。', async () => {
                try {
                    const res = await fetch(`/api/users/${window.currentViewingUserId}/logs/clear`, {method: 'POST'});
                    const result = await res.json();
                    if(result.success) {
                        showToast('用户运行日志已清理完毕', 'success');
                        const tbody = document.getElementById('localHistoryTableBody');
                        if (tbody) tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;">本地运行历史已清空</td></tr>';
                    } else {
                        showToast('清理失败: ' + result.message, 'error');
                    }
                } catch (err) {
                    showToast('网络错误: ' + err.message, 'error');
                }
            });
        }

        // Close modal on click outside
        document.querySelectorAll('.modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', e => {
                if (e.target === overlay) closeModal(overlay.id);
            });
        });

        async function testQQNotify(type) {
            const qqNumber = document.getElementById(`${type}_qq_number`).value;
            const notifyType = document.getElementById(`${type}_qq_notify_type`).value;

            if (!qqNumber) {
                showAlert('请填写 QQ 号/群号');
                return;
            }

            try {
                const formData = new FormData();
                formData.append('qq_number', qqNumber);
                formData.append('qq_notify_type', notifyType);

                const response = await fetch('/test_qq_notify', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();
                showAlert(result.message);
            } catch (error) {
                showAlert('网络连通异常: ' + error);
            }
        }

        function copyCloudData() {
            if (!window.currentHistoryData || window.currentHistoryData.length === 0) {
                showToast('当前没有可复制的数据', 'error');
                return;
            }
            
            let tsv = "运动结束时间\t状态\t耗时\t配速\t步频\t里程(km)\n";
            
            window.currentHistoryData.forEach(run => {
                let rtime = run.recordEndTime || run.endTime || run.recordDate || "-";
                
                let rawDur = run.duration || 0;
                let durStr = (rawDur === 0) ? "待补全" : (Math.floor(rawDur / 60) + "分" + (rawDur % 60) + "秒");
                
                let rawPace = run.recodePace || 0;
                let paceStr = (rawPace === 0) ? "待补全" : "-";
                if (rawPace > 0) {
                    let m = Math.floor(rawPace);
                    let s = Math.round((rawPace % 1) * 60).toString().padStart(2, '0');
                    paceStr = m + "'" + s + '"';
                }
                
                let cadence = run.recodeCadence || run.cadence || run.stepRate || run.stepNum || run.stepFrequency || run.runSteps || 0;
                if (!cadence && rawDur > 0) {
                    let possibleSteps = run.StepNumber || run.recordStepNum || run.recordStep || run.steps || 0;
                    if (possibleSteps > 0) {
                        cadence = Math.round(possibleSteps / (rawDur / 60));
                    }
                }
                let cadenceStr = cadence > 0 ? cadence : "待补全";
                
                const q = run.qualified;
                const iq = run.isQualified;
                const qs = run.qualifiedStatus;
                const isOkFast = (q == 1 || q == "1" || q === true || iq == 1 || iq == "1" || iq === true || qs == 1 || qs == "1" || qs === "合格");
                let statusStr = isOkFast ? "合格" : "未合格";
                
                let mileage = run.recordMileage || '0';
                
                tsv += `${rtime}\t${statusStr}\t${durStr}\t${paceStr}\t${cadenceStr}\t${mileage}\n`;
            });
            
            navigator.clipboard.writeText(tsv).then(() => {
                showToast('数据已复制到剪贴板，可直接粘贴至 Excel', 'success');
            }).catch(err => {
                showToast('复制失败，请重试或检查浏览器权限', 'error');
            });
        }

        async function viewHistory(userId, username) {
            document.getElementById('historyModalTitle').innerText = '云端记录 - ' + username;
            
            const btn = document.getElementById('loadDetailsBtn');
            btn.innerHTML = '补全信息';
            btn.disabled = false;

            openModal('historyModal');
            document.getElementById('historyLoading').style.display = 'block';
            document.getElementById('historyError').style.display = 'none';
            document.getElementById('historyTableContainer').style.display = 'none';
            document.getElementById('historyTermSelect').style.display = 'none';
            document.getElementById('current_history_user').value = userId;

            try {
                // fetch terms
                const response = await fetch(`/api/users/${userId}/terms`);
                const result = await response.json();

                if (result.success && result.data && result.data.length > 0) {
                    const termData = result.data.map(t => ({ id: t.value, name: t.key }));
                    
                    const termContainer = document.getElementById('history_term_modern_container');
                    termContainer.style.display = 'block';
                    
                    let termMs = ModernSelect.instances.get('history_term_modern_container');
                    const config = {
                        data: termData,
                        originalSelect: document.getElementById('historyTermSelect'),
                        placeholder: '切换学期...',
                        onSelect: () => loadTermHistory(),
                        enableSearch: false,
                        fullScreenMobile: false
                    };
                    
                    if (!termMs) {
                        termMs = new ModernSelect('history_term_modern_container', config);
                    } else {
                        termMs.data = termData;
                        termMs.onSelect = config.onSelect;
                        termMs.init();
                    }
                    
                    document.getElementById('current_history_token').value = result.token;

                    // 默认选择第一个 (由于配置了 onSelect，这会自动触发第一学期的 loadTermHistory)
                    if (termData.length > 0) {
                        termMs.setValue(termData[0].id);
                    }
                } else {
                    document.getElementById('historyLoading').style.display = 'none';
                    document.getElementById('historyError').style.display = 'block';
                    document.getElementById('historyError').innerText = '获取失败: ' + (result.message || '没有任何学期数据');
                }
            } catch (error) {
                document.getElementById('historyLoading').style.display = 'none';
                document.getElementById('historyError').style.display = 'block';
                document.getElementById('historyError').innerText = '网络错误: ' + error;
            }
        }

        function downloadFile(filename, content, type = 'text/csv;charset=utf-8;') {
            const blob = new Blob(type.includes('csv') ? ["\ufeff" + content] : [content], { type: type });
            const link = document.createElement("a");
            const url = URL.createObjectURL(blob);
            link.setAttribute("href", url);
            link.setAttribute("download", filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        function exportLocalHistory() {
            if (!window.currentLocalLogs || window.currentLocalLogs.length === 0) {
                showAlert("没有日志记录可导出");
                return;
            }
            let csv = "记录时间,执行状态,结果输出\n";
            window.currentLocalLogs.forEach(log => {
                let msg = (log.message || "").replace(/"/g, '""');
                csv += `"${log.run_time}","${log.status}","${msg}"\n`;
            });
            downloadFile("本地运行日志.csv", csv);
        }

        async function exportRunDetail(runId, mileage) {
            const userId = document.getElementById('current_history_user').value;
            const termVal = document.getElementById('historyTermSelect').value;
            const token = document.getElementById('current_history_token').value;

            try {
                const url = `/api/users/${userId}/history_detail?term_value=${encodeURIComponent(termVal)}&run_id=${encodeURIComponent(runId)}&token=${encodeURIComponent(token)}`;
                const response = await fetch(url);
                const result = await response.json();

                if (result.success) {
                    const dataStr = JSON.stringify(result.data, null, 2);
                    downloadFile(`tasklist_${mileage}km_${runId}.json`, dataStr, 'application/json');
                } else {
                    showAlert("获取路线配置失败: " + result.message);
                }
            } catch (err) {
                showAlert("网络或导出异常: " + err);
            }
        }

        async function viewLocalHistory(userId, username) {
            window.currentViewingUserId = userId;
            document.getElementById('localHistoryModalTitle').innerText = `运行日志 - ${username}`;
            document.getElementById('localHistoryLoading').style.display = 'block';
            document.getElementById('localHistoryTableContainer').style.display = 'none';
            document.getElementById('localHistoryError').style.display = 'none';

            openModal('localHistoryModal');

            try {
                const response = await fetch(`/api/users/${userId}/local_logs`);
                const result = await response.json();

                if (result.success) {
                    window.currentLocalLogs = result.data;
                    document.getElementById('exportLocalHistoryBtn').style.display = 'block';
                    document.getElementById('clearLocalHistoryBtn').style.display = 'block';

                    const tbody = document.getElementById('localHistoryTableBody');
                    if (!result.data || result.data.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="3"><div class="empty-state">尚无打卡日志记录</div></td></tr>';
                    } else {
                        let html = '';
                        result.data.forEach(log => {
                            let badgeHtml = '';
                            if (log.status === 'Success') badgeHtml = '<span class="badge badge-success">Success</span>';
                            else if (log.status === 'Running') badgeHtml = '<span class="badge badge-info">Running</span>';
                            else if (log.status === 'Pending') badgeHtml = '<span class="badge badge-warning">Pending</span>';
                            else if (log.status === 'Failed') badgeHtml = '<span class="badge badge-error">Failed</span>';
                            else badgeHtml = `<span class="badge badge-danger">${log.status}</span>`;

                            html += `<tr>
                                <td data-label="记录时间" style="color:var(--text-muted); font-size:13px;">${log.run_time}</td>
                                <td data-label="执行状态">${badgeHtml}</td>
                                <td data-label="结果输出">
                                    <div style="background:rgba(0,0,0,0.2); padding:8px; border-radius:6px; font-family:monospace; font-size:12px; white-space:pre-wrap; word-break:break-all; color:var(--text-secondary);">${log.message}</div>
                                </td>
                            </tr>`;
                        });
                        tbody.innerHTML = html;
                    }
                    document.getElementById('localHistoryLoading').style.display = 'none';
                    document.getElementById('localHistoryTableContainer').style.display = 'block';
                } else {
                    document.getElementById('localHistoryLoading').style.display = 'none';
                    document.getElementById('localHistoryError').style.display = 'block';
                    document.getElementById('localHistoryError').innerText = '数据获取失败: ' + (result.message || '未知错误');
                }
            } catch (error) {
                document.getElementById('localHistoryLoading').style.display = 'none';
                document.getElementById('localHistoryError').style.display = 'block';
                document.getElementById('localHistoryError').innerText = '网络异常: ' + error;
            }
        }

        async function loadTermHistory() {
            document.getElementById('historyLoading').style.display = 'block';
            document.getElementById('historyTableContainer').style.display = 'none';
            document.getElementById('historyError').style.display = 'none';

            try {
                const userId = document.getElementById('current_history_user').value;
                const termVal = document.getElementById('historyTermSelect').value;
                const token = document.getElementById('current_history_token').value;

                const url = `/api/users/${userId}/history_by_term?term_value=${encodeURIComponent(termVal)}&token=${encodeURIComponent(token)}`;
                const response = await fetch(url);
                const result = await response.json();

                if (result.success) {
                    window.currentHistoryData = result.data;
                    const tbody = document.getElementById('historyTableBody');
                    let termHtml = '<div>';

                    let totalRuns = result.data ? result.data.length : 0;
                    let qualifiedRuns = 0;
                    if (result.data) {
                        qualifiedRuns = result.data.filter(run => {
                            const q = run.qualified;
                            const iq = run.isQualified;
                            const qs = run.qualifiedStatus;
                            return (q == 1 || q == "1" || q === true ||
                                iq == 1 || iq == "1" || iq === true ||
                                qs == 1 || qs == "1" || qs === "合格");
                        }).length;
                    }

                    document.getElementById('termStats').style.display = 'flex';
                    document.getElementById('termTotalRuns').innerText = totalRuns;
                    document.getElementById('termQualifiedCount').innerText = qualifiedRuns;

                    if (!result.data || result.data.length === 0) {
                        termHtml += `<div class="empty-state" style="padding:20px;">该学期尚无相关打卡记录</div>`;
                    } else {
                        termHtml += '<div class="table-responsive" style="margin-bottom:0;"><table id="historyTable"><thead><tr><th>运动结束时间</th><th>状态</th><th>耗时</th><th>配速</th><th>步频</th><th>里程</th></tr></thead><tbody>';
                        result.data.forEach(run => {
                            let rtime = run.recordEndTime || run.endTime || run.recordDate || "-";
                            let displayTime = rtime;
                            if (rtime.includes(" ")) {
                                let parts = rtime.split(" ");
                                displayTime = `<div>${parts[0]}</div><div style="color:var(--text-secondary); font-size:0.9em; margin-top:2px;">${parts[1]}</div>`;
                            }

                            let rawDur = run.duration || 0;
                            let durDisplay = (rawDur === 0) ? '<span style="color:var(--text-secondary); font-size:0.9em;">待补全</span>' : (Math.floor(rawDur / 60) + "分" + (rawDur % 60) + "秒");

                            let rawPace = run.recodePace || 0;
                            let paceDisplay = (rawPace === 0) ? '<span style="color:var(--text-secondary); font-size:0.9em;">待补全</span>' : "-";
                            if (rawPace > 0) {
                                let m = Math.floor(rawPace);
                                let s = Math.round((rawPace % 1) * 60).toString().padStart(2, '0');
                                paceDisplay = m + "'" + s + '"';
                            }
                            
                            let cadence = run.recodeCadence || run.cadence || run.stepRate || run.stepNum || run.stepFrequency || run.runSteps || 0;
                            // 尝试通过可能的步数字段和耗时计算步频
                            if (!cadence && rawDur > 0) {
                                let possibleSteps = run.StepNumber || run.recordStepNum || run.recordStep || run.steps || 0;
                                if (possibleSteps > 0) {
                                    cadence = Math.round(possibleSteps / (rawDur / 60));
                                }
                            }
                            let cadenceDisplay = cadence > 0 ? `<span style="font-size:1em">${cadence}</span> <span style="font-size:0.8em; color:var(--text-secondary)">步/分</span>` : '<span style="color:var(--text-secondary); font-size:0.9em;">待补全</span>';

                            // If the list API already provides it (sometimes it does as 'qualified')
                            const q = run.qualified;
                            const iq = run.isQualified;
                            const isOkFast = (q == 1 || q == "1" || q === true || iq == 1 || iq == "1" || iq === true);
                            
                            let statusDisplay = '<span class="badge badge-error" id="status_' + run.id + '">未合格</span>';
                            if (isOkFast) {
                                statusDisplay = '<span class="badge badge-success" id="status_' + run.id + '">合格</span>';
                            }

                            termHtml += `<tr style="cursor: pointer;" onclick="previewCloudRoute('${run.id}', '${run.recordMileage || 0}')">
                                <td data-label="结束时间" style="color:var(--text-main);">${displayTime}</td>
                                <td data-label="状态">${statusDisplay}</td>
                                <td data-label="耗时" id="dur_${run.id}">${durDisplay}</td>
                                <td data-label="配速" id="pace_${run.id}">${paceDisplay}</td>
                                <td data-label="步频" id="cadence_${run.id}">${cadenceDisplay}</td>
                                <td data-label="里程" style="color:var(--success); font-weight:500;">${run.recordMileage || '0'} km</td>
                            </tr>`;
                        });
                        termHtml += '</tbody></table></div>';
                    }
                    termHtml += '</div>';
                    tbody.innerHTML = termHtml;

                    document.getElementById('historyLoading').style.display = 'none';
                    document.getElementById('historyTableContainer').style.display = 'block';
                    document.getElementById('historyButtonsWrapper').style.display = 'flex';
                } else {
                    document.getElementById('historyLoading').style.display = 'none';
                    document.getElementById('historyError').style.display = 'block';
                    document.getElementById('historyError').innerText = '学期记录提取失败: ' + (result.message || '未知错误');
                }
            } catch (error) {
                document.getElementById('historyLoading').style.display = 'none';
                document.getElementById('historyError').style.display = 'block';
                document.getElementById('historyError').innerText = '网络异常: ' + error;
            }
        }

        async function editUser(userId) {
            try {
                const response = await fetch(`/api/users/${userId}`);
                const user = await response.json();

                document.getElementById('edit_user_id').value = user.id;
                const ms = ModernSelect.instances.get('edit_school_select_modern');
                if (ms) {
                    ms.setValue(user.school_id || '');
                } else {
                    document.getElementById('edit_school_id').value = user.school_id || '';
                }
                document.getElementById('edit_username').value = user.username;
                document.getElementById('edit_yun_username').value = user.yun_username;
                document.getElementById('edit_yun_password').value = ''; // Don't show password
                document.getElementById('edit_qq_number').value = user.qq_number;
                document.getElementById('edit_qq_notify_type').value = user.qq_notify_type;

                openModal('editUserModal');
            } catch (error) {
                showAlert('获取用户信息失败: ' + error);
            }
        }

        async function validateCredentials(type) {
            const username = document.getElementById(`${type}_yun_username`).value;
            const password = document.getElementById(`${type}_yun_password`).value;
            const school_id = document.getElementById(`${type}_school_id`).value;
            const msgDiv = document.getElementById(`${type}_validation_msg`);
            const btn = document.getElementById(`${type}_validate_btn`);

            if (!username || (type === 'add' && !password)) {
                msgDiv.innerHTML = '<span style="color:var(--danger)">请先填写学号和密码</span>';
                return;
            }

            btn.disabled = true;
            btn.innerHTML = '正在验证...';
            msgDiv.innerHTML = '<span style="color:var(--warning)">正在连接云运动服务器...</span>';

            try {
                const formData = new FormData();
                formData.append('yun_username', username);
                formData.append('yun_password', password);
                formData.append('school_id', school_id);

                const response = await fetch('/users/validate', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();

                if (result.success) {
                    msgDiv.innerHTML = `<span style="color:var(--success)">${result.message}</span>`;
                } else {
                    msgDiv.innerHTML = `<span style="color:var(--danger)">${result.message}</span>`;
                }
            } catch (error) {
                msgDiv.innerHTML = `<span style="color:var(--danger)">请求失败: ${error}</span>`;
            } finally {
                btn.disabled = false;
                btn.innerHTML = '验证登录';
            }
        }

        // ================= Tab System =================
        function switchTab(tabId) {
            document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-tab').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-pane-' + tabId).classList.add('active');
            document.getElementById('tab-btn-' + tabId).classList.add('active');

            localStorage.setItem('activeTab', tabId);

            // 切换到日志页时回到顶部（日志面板有独立的内部滚动容器，不需要隐藏外部滚动条）
            if (tabId === 'logs') {
                window.scrollTo(0, 0);
            }

            if (tabId === 'logs') {
                fetchLogs(true);
                if (window.logInterval) clearInterval(window.logInterval);
                const isAuto = document.getElementById('autoRefreshLogToggle')?.checked ?? true;
                if (isAuto) {
                    window.logInterval = setInterval(() => fetchLogs(false), 2000);
                }
            } else if (tabId === 'schedules') {
                if (window.logInterval) clearInterval(window.logInterval);
                loadRouteGroups();
            } else if (tabId === 'routes') {
                if (window.logInterval) clearInterval(window.logInterval);
                loadRouteGroups();
            } else {
                if (window.logInterval) clearInterval(window.logInterval);
            }
        }

        function toggleAutoRefreshLogs() {
            const isAuto = document.getElementById('autoRefreshLogToggle').checked;
            if (window.logInterval) clearInterval(window.logInterval);
            if (isAuto) {
                window.logInterval = setInterval(() => fetchLogs(false), 2000);
                fetchLogs(true);
            }
        }

        async function fetchLogs(force = false) {
            const contentEl = document.getElementById("logContent");
            if (!contentEl) return;

            // 只有在没有手动选中文本，或者是强制刷新（切换Tab/开关打开）时才更新
            const selection = window.getSelection().toString().trim();
            if (selection && !force) return;

            const wasAtBottom = (contentEl.scrollHeight - contentEl.scrollTop <= contentEl.clientHeight + 10);

            try {
                const response = await fetch('/api/logs/stream');
                const result = await response.json();
                if (result.success) {
                    // 仅当内容实际变化或是强制刷新时才操作 DOM
                    if (contentEl.innerText !== result.data || force) {
                        contentEl.innerText = result.data;
                        if (wasAtBottom) {
                            contentEl.scrollTop = contentEl.scrollHeight;
                        }
                    }
                } else {
                    if (!selection) contentEl.innerText = "日志获取失败: " + result.data;
                }
            } catch (e) {
                if (!selection) contentEl.innerText = "网络通讯异常: " + e;
            }
        }

        // ================= Route Management =================
        async function loadRouteGroups() {
            const container = document.getElementById('routesTableContainer');
            if (!document.getElementById('routeGroupsTableBody')) {
                container.innerHTML = `
                    <table style="table-layout: fixed; width: 100%;">
                        <thead>
                            <tr>
                                <th style="width: 40%">路线文件 / 编组</th>
                                <th style="width: 8%">耗时</th>
                                <th style="width: 9%">配速</th>
                                <th style="width: 9%">步频</th>
                                <th style="width: 8%">里程</th>
                                <th style="width: 26%">操作</th>
                            </tr>
                        </thead>
                        <tbody id="routeGroupsTableBody">
                            <tr><td colspan="6"><div class="empty-state">正在加载路线库数据...</div></td></tr>
                        </tbody>
                    </table>
                `;
            }
            const tbody = document.getElementById('routeGroupsTableBody');
            tbody.innerHTML = '<tr><td colspan="6"><div class="empty-state">正在加载路线库数据...</div></td></tr>';
            try {
                const res = await fetch('/api/route_groups');
                const result = await res.json();
                if (result.success) {
                    window.availableGroups = result.data.map(g => g.name);
                    if (result.data.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="6"><div class="empty-state">尚未创建任何路线组文件夹</div></td></tr>';
                    } else {
                        let html = '';
                        result.data.forEach(g => {
                            const safeGroupName = safeJS(g.name);
                            html += `
                                <tr class="group-row" style="cursor: pointer; background-color: rgba(255,255,255,0.05);" onclick="toggleRouteGroupRows('${safeGroupName}')">
                                    <td data-label="路线组">
                                        <div style="display:flex; flex-direction:column; gap:4px;">
                                            <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px;">
                                                <i class="fas fa-folder" id="route-icon-${safeGroupName}" style="color:#fbbf24; font-size:16px;"></i>
                                                <span style="font-size: 15px; font-weight: bold; color:var(--text-main); letter-spacing: 0.3px;">${g.name}</span>
                                                <span style="background:rgba(16,185,129,0.1); color:var(--success); padding:1px 10px; border-radius:12px; font-weight:500; font-size:11px; border:1px solid rgba(16,185,129,0.2);">
                                                    包含 ${g.count} 条路线
                                                </span>
                                            </div>
                                        </div>
                                    </td>
                                    <td data-label="耗时">-</td>
                                    <td data-label="配速">-</td>
                                    <td data-label="步频">-</td>
                                    <td data-label="里程">-</td>
                                    <td>
                                        <div class="action-cell" style="display:flex; gap:8px; flex-wrap:nowrap; overflow:visible;" onclick="event.stopPropagation();">
                                            <button class="btn btn-warning btn-sm" style="white-space:nowrap;" onclick="renameRouteGroup('${safeGroupName}')">重命名</button>
                                            <button class="btn btn-danger btn-sm" style="white-space:nowrap;" onclick="deleteRouteGroup('${safeGroupName}')">全组删除</button>
                                        </div>
                                    </td>
                                </tr>
                            `;
                            if (g.routes && g.routes.length > 0) {
                                g.routes.forEach(f => {
                                    const safeFileName = safeJS(f.filename);
                                    let durDisplay = "-";
                                    if (f.duration) durDisplay = Math.floor(f.duration) + "分" + Math.round((f.duration % 1) * 60) + "秒";
                                    let paceDisplay = "-";
                                    if (f.recode_pace) paceDisplay = Math.floor(f.recode_pace) + "'" + Math.round((f.recode_pace % 1) * 60).toString().padStart(2, '0') + '"';
                                    html += `
                                        <tr class="child-row route-child-${safeGroupName}" style="display: none; background-color: rgba(0,0,0,0.2);">
                                            <td data-label="路线文件" style="padding-left: 40px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                                                <i class="fas fa-map-marked-alt" style="color:var(--text-muted); margin-right:8px;"></i>
                                                ${f.filename} <span style="font-size:11px; color:var(--text-muted);">(${f.size_kb} KB)</span>
                                            </td>
                                            <td data-label="耗时">${durDisplay}</td>
                                            <td data-label="配速">${paceDisplay}</td>
                                            <td data-label="步频">${f.recode_cadence ? `<span style="font-size:13px">${f.recode_cadence}</span><span style="font-size:11px; color:var(--text-secondary)"> 步/分</span>` : '-'}</td>
                                            <td data-label="里程" style="color:var(--success);">${f.recode_mileage ? f.recode_mileage + ' km' : '-'}</td>
                                            <td>
                                                <div class="action-cell" style="display:flex; gap:8px; flex-wrap:nowrap; overflow:visible;" onclick="event.stopPropagation();">
                                                    <button class="btn btn-info btn-xs" style="white-space:nowrap;" onclick="previewRoute('${safeGroupName}', '${safeFileName}')">预览</button>
                                                    <button class="btn btn-warning btn-xs" style="white-space:nowrap;" onclick="renameRouteFile('${safeGroupName}', '${safeFileName}')">重命名</button>
                                                    <button class="btn btn-danger btn-xs" style="white-space:nowrap;" onclick="deleteRouteFile('${safeGroupName}', '${safeFileName}')">删除</button>
                                                </div>
                                            </td>
                                        </tr>
                                    `;
                                });
                            } else {
                                html += `
                                    <tr class="child-row route-child-${safeGroupName}" style="display: none; background-color: rgba(0,0,0,0.2);">
                                        <td colspan="6" style="text-align:center; padding-left: 40px; color:var(--text-muted);">此组内暂无路线 JSON 文件</td>
                                    </tr>
                                `;
                            }
                        });
                        tbody.innerHTML = html;
                    }

                    // Automatically update the options in schedule panels
                    updateScheduleRouteOptions(window.availableGroups || []);
                    // Also refresh schedules to handle "Deleted" state
                    loadSchedules();
                } else {
                    tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state" style="color:var(--danger)">加载失败: ${result.message}</div></td></tr>`;
                    window.availableGroups = [];
                }
            } catch (e) {
                console.error("加载路线库失败:", e);
                tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state" style="color:var(--danger)">网络异常: ${e}</div></td></tr>`;
                window.availableGroups = [];
            }
        }

        function updateScheduleRouteOptions(groupNames) {
            const routeData = groupNames.map(g => ({ id: g, name: g }));
            const addSel = document.getElementById('add_sched_route');
            const editSel = document.getElementById('edit_sched_route');

            // 更新或初始化添加界面的 ModernSelect
            if (addSel) {
                let addMs = ModernSelect.instances.get('add_sched_route_modern');
                if (!addMs) {
                    addMs = new ModernSelect('add_sched_route_modern', {
                        data: routeData,
                        originalSelect: addSel,
                        placeholder: '请选择路线组...'
                    });
                } else {
                    addMs.data = routeData;
                    addMs.init();
                }
            }

            // 更新或初始化编辑界面的 ModernSelect
            if (editSel) {
                let editMs = ModernSelect.instances.get('edit_sched_route_modern');
                if (!editMs) {
                    editMs = new ModernSelect('edit_sched_route_modern', {
                        data: routeData,
                        originalSelect: editSel,
                        placeholder: '请选择路线组...',
                        enableSearch: false,
                        fullScreenMobile: false
                    });
                } else {
                    editMs.data = routeData;
                    editMs.init();
                }
            }

            const options = groupNames.map(g => `<option value="${g}">${g}</option>`).join('');
            if (addSel) addSel.innerHTML = options;
            if (editSel) editSel.innerHTML = options;
        }

        function createRouteGroup() {
            showInputModal('建立新路线组', '路线组目录名:', '', async (name) => {
                try {
                    const res = await fetch('/api/route_groups', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name })
                    });
                    const result = await res.json();
                    if (result.success) {
                        showToast('路线组创建成功！', 'success');
                        loadRouteGroups();
                    } else {
                        showAlert('创建失败: ' + result.message);
                    }
                } catch (e) {
                    showAlert('网络异常: ' + e);
                }
            });
        }

        async function previewCloudRoute(runId, mileage) {
            const userId = document.getElementById('current_history_user').value;
            const termVal = document.getElementById('historyTermSelect').value;
            const token = document.getElementById('current_history_token').value;
            try {
                const detailUrl = `/api/users/${userId}/history_detail?term_value=${encodeURIComponent(termVal)}&run_id=${encodeURIComponent(runId)}&token=${encodeURIComponent(token)}`;
                const res = await fetch(detailUrl);
                const result = await res.json();
                
                if (result.success && result.data && result.data.data && result.data.data.pointsList) {
                    const points = result.data.data.pointsList;
                    if (points.length === 0) {
                        showAlert("该云端记录没有有效的坐标点 (pointsList = 0)");
                        return;
                    }

                    const modal = ensureMapModal();

                    //绑定并显示入库按钮
                    const importBtn = document.getElementById('importInPreviewBtn');
                    if (importBtn) {
                        importBtn.style.display = 'block';
                        importBtn.onclick = () => promptSaveRoute(runId, mileage);
                    }

                    document.getElementById('mapPreviewTitle').innerText = "云端轨迹解密渲染中...";
                    modal.classList.add('active');

                    let latLngs = parsePointsToLatLngs(points);

                    document.getElementById('mapPreviewTitle').innerText = "云端记录 [" + runId + "] 轨迹概览";

                    initMapAndDraw(latLngs);
                } else {
                    showAlert('无法读取该记录的路线详情或其为空（官方数据格式无 pointsList）');
                }
            } catch(e) {
                showAlert('网络异常：' + e);
            }
        }

        async function promptSaveRoute(runId, mileage) {
            try {
                const res = await fetch('/api/route_groups');
                const result = await res.json();
                if (result.success) {
                    if (result.data.length === 0) {
                        showAlert("现在还没有任何路线组！请先在【路线库管理】中创建一个组。");
                        return;
                    }

                    const groupData = result.data.map(g => ({ id: g.name, name: g.name }));
                    let ms = ModernSelect.instances.get('save_route_group_modern');
                    if (!ms) {
                        ms = new ModernSelect('save_route_group_modern', {
                            data: groupData,
                            originalSelect: document.getElementById('save_route_group_select'),
                            placeholder: '请选择目标路线组...',
                            enableSearch: false,
                            fullScreenMobile: false
                        });
                    } else {
                        ms.data = groupData;
                        ms.init();
                    }
                    
                    // 默认选择第一个
                    ms.setValue(groupData[0].id);

                    document.getElementById('save_route_run_id').value = runId;
                    document.getElementById('save_route_mileage').value = mileage;
                    openModal('saveRouteModal');
                } else {
                    showAlert("获取路线组失败: " + result.message);
                }
            } catch (e) {
                showAlert("网络异常: " + e);
            }
        }

        async function executeSaveRoute() {
            const groupName = document.getElementById('save_route_group_select').value;
            const runId = document.getElementById('save_route_run_id').value;
            const mileage = document.getElementById('save_route_mileage').value;

            const userId = document.getElementById('current_history_user').value;
            const termVal = document.getElementById('historyTermSelect').value;
            const token = document.getElementById('current_history_token').value;

            const btn = document.getElementById('save_route_btn');
            btn.innerHTML = '正在拉取写入...';
            btn.disabled = true;

            try {
                // Fetch the actual raw GPS nodes first
                const detailUrl = `/api/users/${userId}/history_detail?term_value=${encodeURIComponent(termVal)}&run_id=${encodeURIComponent(runId)}&token=${encodeURIComponent(token)}`;
                const detailRes = await fetch(detailUrl);
                const detailResult = await detailRes.json();

                if (!detailResult.success) {
                    showAlert("官方原始路线拉取/解密失败: " + detailResult.message);
                    return;
                }

                // Save it to our specific Route Group Route API
                const saveUrl = `/api/route_groups/${encodeURIComponent(groupName)}/save`;
                const saveRes = await fetch(saveUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        filename: `tasklist_${runId}.json`,
                        content: detailResult.data
                    })
                });
                const saveResult = await saveRes.json();
                if (saveResult.success) {
                    showToast("路线落盘保存成功！已入库。", 'success');
                    closeModal('saveRouteModal');
                } else {
                    showAlert("服务器落盘写入失败: " + saveResult.message);
                }
            } catch (e) {
                showAlert("流程异常: " + e);
            } finally {
                btn.innerHTML = '确定保存';
                btn.disabled = false;
            }
        }

        function toggleRouteGroupRows(groupName) {
            const rows = document.querySelectorAll('.route-child-' + groupName);
            const icon = document.getElementById('route-icon-' + groupName);
            let isExpanded = false;
            rows.forEach(row => {
                if (row.style.display === 'none') {
                    row.style.display = 'table-row';
                    isExpanded = true;
                } else {
                    row.style.display = 'none';
                }
            });
            if (isExpanded) {
                icon.classList.remove('fa-folder');
                icon.classList.add('fa-folder-open');
            } else {
                icon.classList.remove('fa-folder-open');
                icon.classList.add('fa-folder');
            }
        }

        function renameRouteGroup(oldName) {
            showInputModal('路线组重命名', `将路线组 ${oldName} 重命名为:`, oldName, async (newName) => {
                if (newName === oldName) return;
                try {
                    const res = await fetch(`/api/route_groups/${encodeURIComponent(oldName)}/rename_group`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ new_name: newName })
                    });
                    const result = await res.json();
                    if (result.success) {
                        showToast('路线组重命名成功', 'success');
                        loadRouteGroups();
                        // Hard refresh to reload mapping inside Schedule table
                        setTimeout(() => window.location.reload(), 800);
                    } else {
                        showAlert("重命名失败: " + result.message);
                    }
                } catch (e) {
                    showAlert("网络异常: " + e);
                }
            });
        }

        async function reloadGroupViewAfterOperation(groupName) {
            loadRouteGroups();
        }

        function renameRouteFile(groupName, filename) {
            showInputModal('路线重命名', `将 ${filename} 重命名为:`, filename, async (newName) => {
                if (newName === filename) return;
                try {
                    const res = await fetch(`/api/route_groups/${encodeURIComponent(groupName)}/${encodeURIComponent(filename)}/rename`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ new_name: newName })
                    });
                    const result = await res.json();
                    if (result.success) {
                        showToast('路线重命名成功', 'success');
                        reloadGroupViewAfterOperation(groupName);
                    } else {
                        showAlert("重命名失败: " + result.message);
                    }
                } catch (e) {
                    showAlert("网络异常: " + e);
                }
            });
        }

        async function toggleTaskActive(scheduleId, checkbox) {
            const originalState = !checkbox.checked;
            try {
                const res = await fetch(`/api/schedules/${scheduleId}/toggle_active`, { method: 'POST' });
                const data = await res.json();
                if (!data.success) {
                    showAlert("状态更新失败: " + data.message);
                    checkbox.checked = originalState;
                }
            } catch (e) {
                showAlert("网络错误");
                checkbox.checked = originalState;
            }
        }
        
        function toggleGroupRows(groupId) {
            const rows = document.querySelectorAll('.child-' + groupId);
            const icon = document.getElementById('icon-' + groupId);
            let isExpanded = false;
            rows.forEach(r => {
                if (r.style.display === 'none') {
                    r.style.display = 'table-row';
                    if(icon) icon.className = 'fas fa-chevron-down';
                } else {
                    r.style.display = 'none';
                    if(icon) icon.className = 'fas fa-chevron-right';
                }
            });
        }
        
        function editGroup(groupId, groupName, time, route, delay, userIdsStr, runDaysStr) {
            document.getElementById('edit_group_id').value = groupId;
            document.getElementById('edit_group_name').value = groupName !== 'null' && groupName !== 'undefined' ? groupName : '';
            document.getElementById('edit_sched_time').value = time;
            
            // 更新 ModernSelect 的值
            const ms = ModernSelect.instances.get('edit_sched_route_modern');
            if (ms) {
                ms.setValue(route);
            } else {
                document.getElementById('edit_sched_route').value = route;
            }
            
            document.getElementById('edit_sched_delay').value = delay;
            
            const userIds = JSON.parse(decodeURIComponent(userIdsStr));
            document.querySelectorAll('.edit-group-user-cb').forEach(cb => {
                cb.checked = userIds.includes(parseInt(cb.value));
            });

            if (runDaysStr === 'undefined' || runDaysStr === null || runDaysStr === '') {
                runDaysStr = '1,2,3,4,5,6,7';
            }
            const runDays = runDaysStr.split(',');
            document.querySelectorAll('.edit-group-rundays-cb').forEach(cb => {
                cb.checked = runDays.includes(cb.value);
            });

            openModal('editScheduleModal');
        }

        /**
         * ModernSelect - 现代感的高性能可搜索选择器
         */
        class ModernSelect {
            static instances = new Map();
            
            constructor(containerId, options = {}) {
                this.container = document.getElementById(containerId);
                this.originalSelect = options.originalSelect; // 原始隐藏的选择框
                this.data = options.data || []; // [{id, name}, ...]
                this.placeholder = options.placeholder || '请搜索...';
                this.enableIndex = options.enableIndex || false;
                
                // 新增选项：控制搜索框和移动端全屏
                this.enableSearch = options.enableSearch !== undefined ? options.enableSearch : true;
                this.fullScreenMobile = options.fullScreenMobile !== undefined ? options.fullScreenMobile : true;
                this.desktopModal = options.desktopModal !== undefined ? options.desktopModal : false;

                this.onSelect = options.onSelect || (() => {});
                this.selectedValue = options.value || '';
                
                this.filteredData = [...this.data];
                this.isOpen = false;
                
                // 拼音首字母边界
                this.pinyinBounds = {
                    'A': '阿', 'B': '八', 'C': '嚓', 'D': '哒', 'E': '妸', 'F': '发', 'G': '旮',
                    'H': '铪', 'I': '丌', 'J': '丌', 'K': '咔', 'L': '垃', 'M': '嘸', 'N': '拿', 'O': '讴',
                    'P': '趴', 'Q': '七', 'R': '呥', 'S': '仨', 'T': '他', 'U': '屲', 'V': '屲', 'W': '屲', 'X': '夕',
                    'Y': '丫', 'Z': '帀'
                };
                this.letters = Object.keys(this.pinyinBounds);
                this.lastTouchLetter = null;

                this.init();
                ModernSelect.instances.set(containerId, this);
            }

            getLetter(str) {
                if (!str) return '#';
                const char = str.charAt(0);
                if (/[a-zA-Z]/.test(char)) return char.toUpperCase();
                
                let lastLetter = '#';
                for (const [letter, bound] of Object.entries(this.pinyinBounds)) {
                    if (char.localeCompare(bound, 'zh-Hans-CN') >= 0) {
                        lastLetter = letter;
                    } else {
                        break;
                    }
                }
                return lastLetter;
            }

            init() {
                // 排序数据
                const collator = new Intl.Collator('zh-Hans-CN', { numeric: true, sensitivity: 'base' });
                this.data.sort((a, b) => collator.compare(a.name, b.name));
                this.filteredData = [...this.data];

                this.render();
                this.bindEvents();
            }

            render() {
                const selectedItem = this.data.find(d => String(d.id) === String(this.selectedValue));
                const displayText = selectedItem ? selectedItem.name : this.placeholder;

                this.container.classList.add('select-search-container');
                if (this.fullScreenMobile) {
                    this.container.classList.add('mobile-fullscreen');
                } else {
                    this.container.classList.remove('mobile-fullscreen');
                }

                this.container.innerHTML = `
                    <div class="select-search-trigger"><span class="select-search-value">${displayText}</span></div>
                    <div class="select-search-dropdown">
                        ${this.enableSearch ? `
                        <div class="select-search-filter">
                            <div class="select-search-close-mobile" style="display:none;">&larr;</div>
                            <input type="text" class="select-search-input" placeholder="输入关键字查找..." spellcheck="false">
                        </div>
                        ` : ''}
                        ${this.enableIndex ? `<div class="select-search-index-bar">${this.letters.map(l => `<span class="index-letter" data-letter="${l}">${l}</span>`).join('')}</div>` : ''}
                        <div class="select-search-options">
                            <div class="options-list"></div>
                        </div>
                        <div class="select-search-touch-indicator"></div>
                    </div>
                `;
                this.renderOptions();
            }

            renderOptions() {
                const root = this._getDropdownRoot();
                const list = root.querySelector('.options-list');
                if (this.filteredData.length === 0) {
                    list.innerHTML = '<div class="select-search-no-results">未找到相关结果</div>';
                    return;
                }

                let html = '';
                let lastGroup = null;

                this.filteredData.forEach(item => {
                    if (this.enableIndex) {
                        const group = this.getLetter(item.name);
                        if (group !== lastGroup) {
                            html += `<div class="select-search-group-title" id="group-${this.container.id}-${group}">${group}</div>`;
                            lastGroup = group;
                        }
                    }
                    
                    const isSelected = String(item.id) === String(this.selectedValue);
                    html += `
                        <div class="select-search-option ${isSelected ? 'selected' : ''}" data-id="${item.id}" data-name="${item.name}">
                            ${item.name}
                        </div>
                    `;
                });
                list.innerHTML = html;
            }

            bindEvents() {
                const trigger = this.container.querySelector('.select-search-trigger');
                const filterInput = this.container.querySelector('.select-search-input');
                const optionsList = this.container.querySelector('.options-list');

                const dropdown = this.container.querySelector('.select-search-dropdown');
                dropdown.onclick = (e) => e.stopPropagation();

                trigger.onclick = (e) => {
                    e.stopPropagation();
                    this.toggle();
                };

                const closeBtn = this.container.querySelector('.select-search-close-mobile');
                if (closeBtn) {
                    closeBtn.onclick = (e) => {
                        e.stopPropagation();
                        this.close();
                    };
                }

                if (filterInput) {
                    filterInput.onclick = (e) => e.stopPropagation();
                    filterInput.oninput = (e) => {
                        const val = e.target.value.toLowerCase().trim();
                        this.filteredData = this.data.filter(d => d.name.toLowerCase().includes(val));
                        this.renderOptions();
                    };
                }

                optionsList.onclick = (e) => {
                    const option = e.target.closest('.select-search-option');
                    if (option) {
                        this.select(option.dataset.id, option.dataset.name);
                    }
                };

                if (this.enableIndex) {
                    const indexBar = this.container.querySelector('.select-search-index-bar');
                    if (indexBar) {
                        const handlePointer = (e) => {
                            // 对于移动事件，只有按下时才触发响应
                            if (e.type === 'pointermove' && e.buttons !== 1) return;
                            
                            e.preventDefault();
                            e.stopPropagation();

                            const rect = indexBar.getBoundingClientRect();
                            const y = e.clientY - rect.top;
                            const percent = Math.min(1, Math.max(0, y / rect.height));
                            // 确保索引在安全范围内
                            const safeIndex = Math.min(this.letters.length - 1, Math.floor(percent * this.letters.length));
                            const letter = this.letters[safeIndex];

                            if (letter && letter !== this.lastTouchLetter) {
                                this.lastTouchLetter = letter;
                                this.scrollToLetter(letter);
                            }
                        };

                        indexBar.addEventListener('pointerdown', (e) => {
                            // 捕获指针，即使滑出元素外界也能收到事件
                            try { indexBar.setPointerCapture(e.pointerId); } catch(err) {}
                            handlePointer(e);
                        });

                        indexBar.addEventListener('pointermove', handlePointer);

                        const handlePointerEnd = (e) => {
                            try { indexBar.releasePointerCapture(e.pointerId); } catch(err) {}
                            const root = this._getDropdownRoot();
                            const indicator = root.querySelector('.select-search-touch-indicator');
                            if (indicator) indicator.style.display = 'none';
                            this.lastTouchLetter = null;
                        };

                        indexBar.addEventListener('pointerup', handlePointerEnd);
                        indexBar.addEventListener('pointercancel', handlePointerEnd);
                        
                        // 防御性组织原生touch影响
                        indexBar.addEventListener('touchstart', e => e.preventDefault(), { passive: false });
                    }
                }

                // 点击外部关闭
                document.addEventListener('click', () => this.close());
            }

            toggle() {
                if (this.isOpen) this.close();
                else this.open();
            }

            open() {
                // 关闭其他实例
                ModernSelect.instances.forEach(ins => { if (ins !== this) ins.close(); });
                
                this.isOpen = true;
                this.container.classList.add('active');

                const isMobile = window.innerWidth <= 768;
                const isFS = (this.fullScreenMobile && isMobile);
                const isDModal = (this.desktopModal && !isMobile);

                // 模态框或全屏模式：将下拉面板移到 body
                if (isFS || isDModal) {
                    const dropdown = this.container.querySelector('.select-search-dropdown');
                    if (dropdown) {
                        this._dropdownOriginalParent = dropdown.parentNode;
                        this._dropdownEl = dropdown;
                        document.body.appendChild(dropdown);

                        // 显示遮罩层
                        this._overlay = document.querySelector('.select-search-overlay');
                        if (!this._overlay) {
                            this._overlay = document.createElement('div');
                            this._overlay.className = 'select-search-overlay';
                            document.body.appendChild(this._overlay);
                        }
                        this._overlay.classList.add('active');
                        this._overlay.onclick = () => this.close();

                        if (isFS) {
                            // 移动端全屏样式
                            dropdown.style.cssText = `
                                display:flex; position:fixed; top:0; left:0;
                                width:100vw; height:100vh; max-height:100vh;
                                z-index:9999; border-radius:0; border:none;
                                overflow:hidden; flex-direction:column;
                                background:#1e293b;
                                overscroll-behavior:none;
                                visibility: visible;
                            `;
                        } else {
                            // 桌面端模态框样式
                            dropdown.classList.add('desktop-modal');
                            dropdown.style.display = 'flex';
                            // 注意：desktop-modal 样式中定义了 visibility: hidden
                        }

                        // 插入顶部标题栏（全屏或模态框均需要）
                        let header = dropdown.querySelector('.fs-header');
                        if (!header) {
                            header = document.createElement('div');
                            header.className = 'fs-header';
                            header.style.cssText = `
                                display:flex; align-items:center; justify-content:space-between;
                                padding:14px 16px; flex-shrink:0;
                                border-bottom:1px solid rgba(255,255,255,0.1);
                            `;
                            header.innerHTML = `
                                <span style="width:28px;"></span>
                                <span style="color:#fff;font-size:16px;font-weight:600;">${isMobile ? "选择学校" : "检索学校"}</span>
                                <span class="fs-cancel" style="display:flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;background:rgba(255,255,255,0.08);color:var(--danger);cursor:pointer;transition:all 0.2s;flex-shrink:0;">
                                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                                </span>
                            `;
                            dropdown.insertBefore(header, dropdown.firstChild);
                            header.querySelector('.fs-cancel').onclick = (e) => {
                                e.stopPropagation();
                                this.close();
                            };
                        }

                        // 隐藏旧的移动端搜索栏关闭按钮
                        const oldCloseBtn = dropdown.querySelector('.select-search-close-mobile');
                        if (oldCloseBtn) oldCloseBtn.style.display = 'none';

                        // 延迟计算以确保 offsetHeight 已就绪
                        setTimeout(() => {
                            const header = dropdown.querySelector('.fs-header');
                            const filter = dropdown.querySelector('.select-search-filter');
                            const opts = dropdown.querySelector('.select-search-options');
                            const idxBar = dropdown.querySelector('.select-search-index-bar');
                            
                            const hHeight = header ? header.offsetHeight : 53;
                            const fHeight = filter ? filter.offsetHeight : 52;
                            const totalTop = hHeight + fHeight;

                            if (opts) {
                                opts.style.maxHeight = `calc(${isFS ? '100vh' : '750px'} - ${totalTop}px)`;
                                opts.style.paddingRight = '44px';
                                opts.style.overflowX = 'hidden';
                                opts.style.flexGrow = '1';
                                opts.style.overflowY = 'auto';
                                opts.style.scrollbarWidth = 'none';
                                opts.style.msOverflowStyle = 'none';
                                opts.style.overscrollBehavior = 'contain';
                            }
                            
                            if (idxBar) {
                                idxBar.style.position = 'absolute';
                                idxBar.style.top = `${totalTop}px`;
                                idxBar.style.right = '0';
                                idxBar.style.bottom = '0';
                                idxBar.style.width = '36px';
                                idxBar.style.display = 'flex';
                                idxBar.style.flexDirection = 'column';
                                idxBar.style.justifyContent = 'space-between';
                                idxBar.style.alignItems = 'center';
                                idxBar.style.padding = '4px 0';
                                idxBar.style.zIndex = '20';
                                idxBar.style.touchAction = 'none';
                                idxBar.style.userSelect = 'none';
                                idxBar.style.background = 'rgba(255,255,255,0.02)';
                                idxBar.style.borderRadius = '0';
                            }
                            
                            // 样式应用并计算完成后，再使桌面弹窗可见
                            if (isDModal) {
                                dropdown.style.visibility = 'visible';
                            }
                        }, 10);
                        this._movedToBody = true;
                        if (typeof lockBodyScroll === 'function') lockBodyScroll(); /* 防止选择学校时背景穿透 */
                    }
                }

                if (this.enableSearch) {
                    const input = (this._movedToBody ? document.body : this.container).querySelector('.select-search-input');
                    if (input) setTimeout(() => input.focus(), 100);
                }
            }

            close() {
                this.isOpen = false;
                this.container.classList.remove('active');

                // 将下拉面板移回原始容器
                if (this._movedToBody && this._dropdownEl) {
                    // 隐藏遮罩层
                    if (this._overlay) this._overlay.classList.remove('active');

                    // 清除所有内联样式（下拉面板 + 子元素）
                    this._dropdownEl.style.cssText = '';
                    this._dropdownEl.classList.remove('desktop-modal');
                    
                    const opts = this._dropdownEl.querySelector('.select-search-options');
                    if (opts) opts.style.cssText = '';
                    const idxBar = this._dropdownEl.querySelector('.select-search-index-bar');
                    if (idxBar) idxBar.style.cssText = '';
                    // 移除全屏标题栏
                    const fsHeader = this._dropdownEl.querySelector('.fs-header');
                    if (fsHeader) fsHeader.remove();
                    // 重置搜索
                    const searchInput = this._dropdownEl.querySelector('.select-search-input');
                    if (searchInput) {
                        searchInput.value = '';
                        this.filteredData = [...this.data];
                        this.renderOptions();
                    }
                    if (this._dropdownOriginalParent) {
                        this._dropdownOriginalParent.appendChild(this._dropdownEl);
                    }
                    this._movedToBody = false;
                    /* 检查是否还有其他模态窗口，如果没有则恢复滚动 */
                    if (!document.querySelector('.select-search-mobile-overlay.active') && 
                        !document.querySelector('.modal-overlay.active')) {
                        if (typeof unlockBodyScroll === 'function') unlockBodyScroll();
                    }
                }
            }

            // 辅助方法：获取当前下拉面板的根节点（可能在 container 或 body 上）
            _getDropdownRoot() {
                if (this._movedToBody && this._dropdownEl) {
                    return this._dropdownEl;
                }
                return this.container;
            }

            scrollToLetter(letter) {
                const root = this._getDropdownRoot();
                let targetEl = root.querySelector(`#group-${this.container.id}-${letter}`);
                
                if (!targetEl) {
                    // 如果当前字母没有对应的学校分组，则向前寻找最近的分组（类似 iOS 通讯录行为）
                    const letterIndex = this.letters.indexOf(letter);
                    for (let i = letterIndex - 1; i >= 0; i--) {
                        targetEl = root.querySelector(`#group-${this.container.id}-${this.letters[i]}`);
                        if (targetEl) break;
                    }
                    if (!targetEl) {
                        // 如果前面没有，再向后找
                        for (let i = letterIndex + 1; i < this.letters.length; i++) {
                            targetEl = this.container.querySelector(`#group-${this.container.id}-${this.letters[i]}`);
                            if (targetEl) break;
                        }
                    }
                }

                if (targetEl) {
                    targetEl.scrollIntoView({ behavior: 'auto', block: 'start' });
                }
                
                // 气泡提示始终显示用户实际触碰的字母，提供确实的反馈
                const indicator = root.querySelector('.select-search-touch-indicator');
                if (indicator) {
                    indicator.innerText = letter;
                    indicator.style.display = 'flex';
                }
            }

            select(id, name) {
                this.selectedValue = id;
                this.container.querySelector('.select-search-value').innerText = name;
                if (this.originalSelect) {
                    this.originalSelect.value = id;
                    this.originalSelect.dispatchEvent(new Event('change'));
                }
                this.onSelect(id, name);
                this.close();
                this.renderOptions(); // 更新选中状态
            }

            setValue(id) {
                const item = this.data.find(d => String(d.id) === String(id));
                if (item) {
                    this.select(id, item.name);
                } else {
                    this.selectedValue = '';
                    this.container.querySelector('.select-search-value').innerText = this.placeholder;
                }
            }
        }

        async function loadSchedules() {
            const tbody = document.getElementById('schedulesTableBody');
            if (!tbody) return;

            try {
                const res = await fetch('/api/schedules');
                const result = await res.json();
                if (result.success) {
                    if (result.data.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="4"><div class="empty-state">尚未创建任何调度规则</div></td></tr>';
                    } else {
                        const groups = {};
                        result.data.forEach(s => {
                            const key = s.group_id || `${s.target_time}-${s.route_type}-${s.random_delay_minutes}`;
                            if (!groups[key]) {
                                groups[key] = {
                                    group_id: s.group_id,
                                    group_name: s.group_name,
                                    target_time: s.target_time,
                                    route_type: s.route_type,
                                    random_delay_minutes: s.random_delay_minutes,
                                    run_days: s.run_days || '1,2,3,4,5,6,7',
                                    tasks: []
                                };
                            }
                            groups[key].tasks.push(s);
                        });
                        
                        let html = '';
                        Object.values(groups).forEach(group => {
                            const userIdsEncoded = encodeURIComponent(JSON.stringify(group.tasks.map(t => t.user_id)));
                            const safeGroupId = safeJS(group.group_id);
                            const safeGroupName = safeJS(group.group_name);
                            const safeRouteType = safeJS(group.route_type);
                            const safeTime = safeJS(group.target_time);
                            const safeRunDays = safeJS(group.run_days);

                            const isMissing = window.availableGroups && !window.availableGroups.includes(group.route_type);
                            const routeDisplay = isMissing ? `<span style="text-decoration:line-through;">${group.route_type}</span>(丢失)` : `${group.route_type}`;

                            html += `
                                <tr class="group-row" style="cursor: pointer; background-color: rgba(255,255,255,0.05);" onclick="toggleGroupRows('${safeGroupId}')">
                                    <td data-label="任务组" style="vertical-align: middle;">
                                        <div style="display:flex; flex-direction:column; gap:4px;">
                                            <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px;">
                                                <i class="fas fa-chevron-right" id="icon-${safeGroupId}" style="margin-right: 2px; width: 14px;"></i>
                                                <span style="font-size: 15px; font-weight: bold; color:var(--text-main);">${group.group_name || '未命名任务组'}</span>
                                                <span style="background:rgba(59,130,246,0.1); color:var(--primary); padding:1px 10px; border-radius:12px; font-weight:500; font-size:11px; border:1px solid rgba(59,130,246,0.2);">
                                                    包含 ${group.tasks.length} 个账户
                                                </span>
                                            </div>
                                            <div style="font-size: 12px; margin-left:24px; color:var(--text-muted); display:flex; align-items:center; gap:12px; margin-top:2px;">
                                                <span style="color:var(--primary); font-weight: 600; background:rgba(59,130,246,0.05); padding:0 4px; border-radius:4px;">${group.target_time}</span>
                                                <span><i class="far fa-clock" style="margin-right:4px; opacity:0.7;"></i>${group.random_delay_minutes}分钟缓冲</span>
                                                <span style="opacity:0.8;"><i class="fas fa-road" style="margin-right:4px; opacity:0.7;"></i>${routeDisplay}</span>
                                            </div>
                                        </div>
                                    </td>
                                    <td data-label="上次状态" style="vertical-align: middle;">-</td>
                                    <td data-label="结束时间" style="vertical-align: middle;">-</td>
                                    <td style="vertical-align: middle;">
                                        <div style="display:flex; gap:8px; flex-wrap:wrap; align-items: center;" onclick="event.stopPropagation();">
                                            <button type="button" class="btn btn-warning btn-sm" style="white-space:nowrap;" onclick="editGroup('${safeGroupId}', '${safeGroupName}', '${safeTime}', '${safeRouteType}', ${group.random_delay_minutes}, '${userIdsEncoded}', '${safeRunDays}')">编辑组</button>
                                            <form id="delete-group-${safeGroupId}" action="/schedules/delete_group" method="POST" style="margin:0;">
                                                <input type="hidden" name="group_id" value="${group.group_id}">
                                                <button type="button" class="btn btn-danger btn-sm" style="white-space:nowrap;" onclick="showConfirmModal('确认删除', '确定要彻底删除该任务组吗？此操作不可恢复。', () => document.getElementById('delete-group-${safeGroupId}').submit())">全组删除</button>
                                            </form>
                                        </div>
                                    </td>
                                </tr>
                            `;
                            
                            group.tasks.forEach(s => {
                                let statusBadge = `<span class="badge badge-neutral">${s.last_run_status}</span>`;
                                if (s.last_run_status === 'Success') statusBadge = '<span class="badge badge-success">Completed</span>';
                                else if (s.last_run_status === 'Failed') statusBadge = '<span class="badge badge-error">Failed</span>';
                                
                                html += `
                                <tr class="child-row child-${safeGroupId}" style="display: none; background-color: rgba(0,0,0,0.2);">
                                    <td data-label="账户" style="padding-left: 40px; vertical-align: middle;">
                                        <div style="display:flex; align-items:center;">
                                            <label class="switch" style="margin-bottom:0;">
                                                <input type="checkbox" ${s.is_active ? 'checked' : ''} onchange="toggleTaskActive(${s.id}, this)">
                                                <span class="slider"></span>
                                            </label>
                                            <span style="margin-left: 10px;">${s.username}</span>
                                        </div>
                                    </td>
                                    <td data-label="上次状态" style="vertical-align: middle;">${statusBadge}</td>
                                    <td data-label="结束时间" class="log-time" style="vertical-align: middle;">${s.last_run_time}</td>
                                    <td style="vertical-align: middle;">
                                        <div style="display:flex; gap:8px; align-items: center;" onclick="event.stopPropagation();">
                                            <form action="/runs/manual_trigger" method="POST" style="margin:0;">
                                                <input type="hidden" name="schedule_id" value="${s.id}">
                                                <button type="submit" class="btn btn-info btn-xs" title="立即无缓冲排队执行此人">立即执行</button>
                                            </form>
                                        </div>
                                    </td>
                                </tr>`;
                            });
                        });
                        tbody.innerHTML = html;
                    }
                } else {
                    tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state" style="color:var(--danger)">加载失败: ${result.message}</div></td></tr>`;
                }
            } catch (e) {
                console.error("加载任务列表失败:", e);
                tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state" style="color:var(--danger)">网络异常: ${e}</div></td></tr>`;
            }
        }

        // Handle initial load
        (async () => {
            // 异步加载学校列表
            let schoolData = [];
            try {
                const res = await fetch('/api/schools');
                const json = await res.json();
                if (json.success && json.data) {
                    schoolData = json.data.map(s => ({ id: s.schoolId, name: s.schoolName }));
                    
                    // 初始化“添加用户”和“编辑用户”的 ModernSelect
                    new ModernSelect('add_school_select_modern', {
                        data: schoolData,
                        originalSelect: document.getElementById('add_school_id'),
                        placeholder: '搜索并选择学校...',
                        enableIndex: true,
                        desktopModal: true
                    });
                    
                    new ModernSelect('edit_school_select_modern', {
                        data: schoolData,
                        originalSelect: document.getElementById('edit_school_id'),
                        placeholder: '搜索并选择学校...',
                        enableIndex: true,
                        desktopModal: true
                    });
                }
            } catch(e) { console.error("加载学校列表失败:", e); }

            // 初始化“推送组”类型选择 ModernSelect
            new ModernSelect('pg_notify_type_modern', {
                data: [
                    { id: 'private', name: '私聊 (个人QQ)' },
                    { id: 'group', name: '群聊 (QQ群号)' },
                    { id: 'tgbot', name: 'Telegram 机器人' }
                ],
                originalSelect: document.getElementById('pg_qq_notify_type'),
                placeholder: '请选择推送类型...',
                enableSearch: false,
                fullScreenMobile: false
            });

            const savedTab = localStorage.getItem('activeTab') || 'accounts';
            switchTab(savedTab);
            
            // 无论当前在哪个标签，都需要拉取路线组字典（任务组管理依赖 availableGroups）
            if (savedTab !== 'routes' && savedTab !== 'schedules') {
                loadRouteGroups();
            }
        })();

        async function deleteRouteGroup(groupName) {
            showConfirmModal('确认删除组', `确定要彻底删除整个 ${groupName} 路线组吗？此操作将物理删除文件夹内所有文件，且不可恢复！`, async () => {
                try {
                    const res = await fetch(`/api/route_groups/${encodeURIComponent(groupName)}`, { method: 'DELETE' });
                    const result = await res.json();
                    if (result.success) {
                        loadRouteGroups();
                    } else {
                        showAlert("删除失败: " + result.message);
                    }
                } catch (e) {
                    showAlert("网络异常: " + e);
                }
            });
        }

        async function deleteRouteFile(groupName, filename) {
            showConfirmModal('确认删除', `确定要从 ${groupName} 路线组中删除 ${filename} 吗？此操作不可恢复。`, async () => {
                try {
                    const res = await fetch(`/api/route_groups/${encodeURIComponent(groupName)}/${encodeURIComponent(filename)}`, { method: 'DELETE' });
                    const result = await res.json();
                    if (result.success) {
                        reloadGroupViewAfterOperation(groupName);
                    } else {
                        showAlert("删除失败: " + result.message);
                    }
                } catch (e) {
                    showAlert("网络异常: " + e);
                }
            });
        }
        async function loadAllRunDetails() {
            if (!window.currentHistoryData || window.currentHistoryData.length === 0) {
                showAlert("当前学期没有任何历史记录");
                return;
            }

            const btn = document.getElementById('loadDetailsBtn');
            btn.disabled = true;
            const originalText = btn.innerHTML;

            const userId = document.getElementById('current_history_user').value;
            const termVal = document.getElementById('historyTermSelect').value;
            const token = document.getElementById('current_history_token').value;

            let loadedCount = 0;
            const totalCount = window.currentHistoryData.length;

            for (let i = 0; i < totalCount; i++) {
                const currentModalUserId = document.getElementById('current_history_user').value;
                if (currentModalUserId !== userId || !document.getElementById('historyModal').classList.contains('active')) {
                    // Modal was closed or user changed, just exit silently.
                    return;
                }

                let run = window.currentHistoryData[i];

                // If it already seems correctly hydrated (not zeroes), skip to save time.
                // But Yun api might natively have zeroes if the run was truly 0 duration, 
                // we'll fetch anyway if it's currently 0 to be sure.
                let currentCadence = run.recodeCadence || run.cadence || run.runSteps || 0;
                if (run.duration > 0 && run.recodePace > 0 && currentCadence > 0) {
                    loadedCount++;
                    continue;
                }

                btn.innerHTML = `正在获取... (${loadedCount + 1}/${totalCount})`;

                try {
                    const url = `/api/users/${userId}/history_detail?term_value=${encodeURIComponent(termVal)}&run_id=${encodeURIComponent(run.id)}&token=${encodeURIComponent(token)}`;
                    const response = await fetch(url);
                    const result = await response.json();

                    if (result.success && result.data && result.data.data) {
                        const runDetail = result.data.data;
                        console.log("Run Detail for " + run.id + ":", runDetail); // Debug

                        run.duration = runDetail.duration || 0;
                        run.recodePace = runDetail.recodePace || 0;
                        run.recodeCadence = runDetail.recodeCadence || runDetail.cadence || runDetail.runSteps || 0;

                        // Robust check for qualification (handle 1, "1", true, etc.)
                        const q = runDetail.qualified;
                        const iq = runDetail.isQualified;
                        const qs = runDetail.qualifiedStatus;

                        const isOk = (q == 1 || q == "1" || q === true ||
                            iq == 1 || iq == "1" || iq === true ||
                            qs == 1 || qs == "1" || qs === "合格");

                        run.qualified = isOk ? 1 : 0;

                        let durDisplay = Math.floor(run.duration / 60) + "分" + (run.duration % 60) + "秒";
                        let paceDisplay = "-";
                        if (run.recodePace > 0) {
                            let m = Math.floor(run.recodePace);
                            let s = Math.round((run.recodePace % 1) * 60).toString().padStart(2, '0');
                            paceDisplay = m + "'" + s + '"';
                        }
                        
                        let cadenceDisplay = '<span style="color:var(--text-secondary); font-size:0.9em;">待补全</span>';
                        if (run.recodeCadence > 0) {
                            cadenceDisplay = `<span style="font-size:1em">${run.recodeCadence}</span> <span style="font-size:0.8em; color:var(--text-secondary)">步/分</span>`;
                        } else if (runDetail.runSteps > 0 && run.duration > 0) {
                            let calculatedCadence = Math.round(runDetail.runSteps / (run.duration / 60));
                            cadenceDisplay = `<span style="font-size:1em">${calculatedCadence}</span> <span style="font-size:0.8em; color:var(--text-secondary)">步/分</span>`;
                            run.recodeCadence = calculatedCadence;
                        }

                        const durTd = document.getElementById(`dur_${run.id}`);
                        const paceTd = document.getElementById(`pace_${run.id}`);
                        const cadenceTd = document.getElementById(`cadence_${run.id}`);
                        const statusSpan = document.getElementById(`status_${run.id}`);

                        if (durTd) durTd.innerHTML = durDisplay;
                        if (paceTd) paceTd.innerHTML = paceDisplay;
                        if (cadenceTd) cadenceTd.innerHTML = cadenceDisplay;
                        if (statusSpan) {
                            if (isOk) {
                                statusSpan.className = 'badge badge-success';
                                statusSpan.innerText = '合格';
                            } else {
                                statusSpan.className = 'badge badge-error';
                                statusSpan.innerText = '未合格';
                            }
                        }
                    }
                } catch (e) {
                    console.error("加载详情失败: ", e);
                }

                loadedCount++;
                // Avoid ratelimiting the Yun server (sleep 650 ms)
                await new Promise(r => setTimeout(r, 650));
            }

            btn.innerHTML = "补全信息完成";
            setTimeout(() => {
                btn.innerHTML = originalText;
                btn.disabled = false;
            }, 3000);
        }
        // --- Route Map Preview Logic ---
        function safeJS(str) {
            if (typeof str !== 'string') return str;
            return str.replace(/'/g, "\\'");
        }

        let mapInstance = null;
        let polylineLayer = null;

        async function previewRoute(groupName, filename) {
        async function previewRoute(groupName, filename) {
            const modal = ensureMapModal();

            document.getElementById('mapPreviewTitle').innerText = filename + " 轨迹预览中...";
            modal.classList.add('active');

            // 路线组预览不需要导入按钮
            const importBtn = document.getElementById('importInPreviewBtn');
            if (importBtn) importBtn.style.display = 'none';

            try {
                const res = await fetch(`/api/route_groups/${encodeURIComponent(groupName)}/${encodeURIComponent(filename)}`);
                const result = await res.json();

                document.getElementById('mapPreviewTitle').innerText = filename + " (路线概览)";

                if (result.success && result.data && result.data.data && result.data.data.pointsList) {
                    const points = result.data.data.pointsList;
                    if (points.length === 0) {
                        showAlert("该文件中没有有效的坐标点 (pointsList = 0)");
                        return;
                    }

                    let latLngs = parsePointsToLatLngs(points);
                    initMapAndDraw(latLngs);
                } else {
                    showAlert("路线解析失败，内部数据格式无 pointsList。");
                }
            } catch (e) {
                showAlert("拉取报错: " + e);
            }
        }

        // --- Shared Map Preview Helpers ---
        let mapInstance = null;
        let polylineLayer = null;

        function ensureMapModal() {
            let modal = document.getElementById('mapPreviewModal');
            if (!modal) {
                const modalHtml = `
                <div class="modal-overlay" id="mapPreviewModal" style="z-index: 200;">
                    <div class="modal-box" style="max-width: 800px; height: 80vh; display:flex; flex-direction:column; padding: 20px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 12px;">
                            <h2 class="panel-title" id="mapPreviewTitle">路线预览</h2>
                            <div style="display:flex; gap: 12px; align-items: center;">
                                <button class="btn btn-secondary btn-sm" id="animPlayBtn" onclick="toggleAnimation()" style="display:none; padding:4px 10px; font-size:12px;">▶ 轨迹动画</button>
                                <button class="btn btn-secondary btn-sm" id="importInPreviewBtn" style="display:none;">导出至路线组</button>
                                <button type="button" onclick="closeMapPreview()" style="display:flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;background:rgba(255,255,255,0.08);color:var(--danger);cursor:pointer;transition:all 0.2s;flex-shrink:0;border:none;">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                                </button>
                            </div>
                        </div>
                        <div id="mapRenderArea" style="flex:1; width: 100%; border-radius: 12px; border: 1px solid var(--glass-border); background: rgba(0,0,0,0.2);"></div>
                    </div>
                </div>`;
                document.body.insertAdjacentHTML('beforeend', modalHtml);
                modal = document.getElementById('mapPreviewModal');
            }
            return modal;
        }

        const GCJ02_PI = 3.1415926535897932384626;
        const GCJ02_A = 6378245.0;
        const GCJ02_EE = 0.00669342162296594323;

        function transformLat(x, y) {
            let ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
            ret += (20.0 * Math.sin(6.0 * x * GCJ02_PI) + 20.0 * Math.sin(2.0 * x * GCJ02_PI)) * 2.0 / 3.0;
            ret += (20.0 * Math.sin(y * GCJ02_PI) + 40.0 * Math.sin(y / 3.0 * GCJ02_PI)) * 2.0 / 3.0;
            ret += (160.0 * Math.sin(y / 12.0 * GCJ02_PI) + 320 * Math.sin(y * GCJ02_PI / 30.0)) * 2.0 / 3.0;
            return ret;
        }

        function transformLng(x, y) {
            let ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
            ret += (20.0 * Math.sin(6.0 * x * GCJ02_PI) + 20.0 * Math.sin(2.0 * x * GCJ02_PI)) * 2.0 / 3.0;
            ret += (20.0 * Math.sin(x * GCJ02_PI) + 40.0 * Math.sin(x / 3.0 * GCJ02_PI)) * 2.0 / 3.0;
            ret += (150.0 * Math.sin(x / 12.0 * GCJ02_PI) + 300.0 * Math.sin(x / 30.0 * GCJ02_PI)) * 2.0 / 3.0;
            return ret;
        }

        function gcj02towgs84(lng, lat) {
            let dlat = transformLat(lng - 105.0, lat - 35.0);
            let dlng = transformLng(lng - 105.0, lat - 35.0);
            let radlat = lat / 180.0 * GCJ02_PI;
            let magic = Math.sin(radlat);
            magic = 1 - GCJ02_EE * magic * magic;
            let sqrtmagic = Math.sqrt(magic);
            dlat = (dlat * 180.0) / ((GCJ02_A * (1 - GCJ02_EE)) / (magic * sqrtmagic) * GCJ02_PI);
            dlng = (dlng * 180.0) / (GCJ02_A / sqrtmagic * Math.cos(radlat) * GCJ02_PI);
            let mglat = lat + dlat;
            let mglng = lng + dlng;
            return [lng * 2 - mglng, lat * 2 - mglat];
        }

        function parsePointsToLatLngs(pointsList) {
            let latLngs = [];
            pointsList.forEach(pt => {
                const coords = pt.point ? pt.point.split(',') : [];
                if (coords.length === 2) {
                    let wgs84Coords = gcj02towgs84(parseFloat(coords[0]), parseFloat(coords[1]));
                    latLngs.push([wgs84Coords[1], wgs84Coords[0]]);
                }
            });
            return latLngs;
        }

        function initMapAndDraw(latLngs) {
            if (!mapInstance) {
                setTimeout(() => {
                    mapInstance = L.map('mapRenderArea');
                    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                        attribution: 'Tiles &copy; Esri',
                        maxZoom: 19
                    }).addTo(mapInstance);
                    drawLine(latLngs);
                }, 50);
            } else {
                setTimeout(() => {
                    mapInstance.invalidateSize();
                    drawLine(latLngs);
                }, 50);
            }
        }

        // --- Track Animation System ---
        let animGhostLine = null;
        let animLine = null;
        let animMarker = null;
        let animStartMarker = null;
        let animEndMarker = null;
        let animFrameId = null;
        let animAllPoints = [];
        let animPlaying = false;
        let animPaused = false;
        let animStartTime = null;
        let animPausedAt = 0;

        function clearAnimation() {
            if (animFrameId) { cancelAnimationFrame(animFrameId); animFrameId = null; }
            [animGhostLine, animLine, animMarker, animStartMarker, animEndMarker, polylineLayer].forEach(layer => {
                if (layer && mapInstance) mapInstance.removeLayer(layer);
            });
            animGhostLine = animLine = animMarker = animStartMarker = animEndMarker = polylineLayer = null;
            animPlaying = false;
            animPaused = false;
            animStartTime = null;
            animPausedAt = 0;
        }

        function drawLine(latLngs) {
            clearAnimation();
            animAllPoints = latLngs;

            // 幽灵轨迹：完整路线的淡色虚线
            animGhostLine = L.polyline(latLngs, {
                color: '#ffffff', weight: 2, opacity: 0.2, dashArray: '6,8'
            }).addTo(mapInstance);

            // 起点标记（绿色）
            animStartMarker = L.circleMarker(latLngs[0], {
                radius: 7, color: '#fff', fillColor: '#22c55e', fillOpacity: 1, weight: 2
            }).addTo(mapInstance);

            // 终点标记（红色）
            animEndMarker = L.circleMarker(latLngs[latLngs.length - 1], {
                radius: 7, color: '#fff', fillColor: '#ef4444', fillOpacity: 1, weight: 2
            }).addTo(mapInstance);

            mapInstance.fitBounds(animGhostLine.getBounds(), { padding: [30, 30] });

            const btn = document.getElementById('animPlayBtn');
            if (btn) { btn.style.display = 'inline-flex'; btn.innerHTML = '⏸ 暂停'; }

            // 自动开始动画
            animPausedAt = 0;
            startTrackAnimation();
        }

        function startTrackAnimation() {
            animPlaying = true;
            animPaused = false;
            animStartTime = null;

            if (animLine) mapInstance.removeLayer(animLine);
            animLine = L.polyline([animAllPoints[0]], {
                color: '#3b82f6', weight: 4.5, opacity: 0.95
            }).addTo(mapInstance);

            if (animMarker) mapInstance.removeLayer(animMarker);
            animMarker = L.circleMarker(animAllPoints[0], {
                radius: 6, color: '#fff', fillColor: '#facc15', fillOpacity: 1, weight: 2
            }).addTo(mapInstance);

            animFrameId = requestAnimationFrame(animateFrame);
        }

        function animateFrame(timestamp) {
            if (!animPlaying || animPaused) return;
            if (!animStartTime) animStartTime = timestamp - (animPausedAt * 6000);

            const elapsed = timestamp - animStartTime;
            const totalDuration = 6000;
            const progress = Math.min(elapsed / totalDuration, 1);
            const targetIndex = Math.floor(progress * (animAllPoints.length - 1));

            animLine.setLatLngs(animAllPoints.slice(0, targetIndex + 1));
            animMarker.setLatLng(animAllPoints[targetIndex]);

            if (progress < 1) {
                animFrameId = requestAnimationFrame(animateFrame);
            } else {
                // 动画结束：显示完整实线并清除跑步者标记
                animPlaying = false;
                animPausedAt = 0;
                if (animMarker) { mapInstance.removeLayer(animMarker); animMarker = null; }
                if (animGhostLine) { mapInstance.removeLayer(animGhostLine); animGhostLine = null; }
                if (animLine) { mapInstance.removeLayer(animLine); animLine = null; }
                polylineLayer = L.polyline(animAllPoints, { color: '#ef4444', weight: 4, opacity: 0.8 }).addTo(mapInstance);
                const btn = document.getElementById('animPlayBtn');
                if (btn) btn.innerHTML = '🔄 重播';
            }
        }

        function toggleAnimation() {
            if (!animAllPoints || animAllPoints.length === 0) return;
            const btn = document.getElementById('animPlayBtn');

            if (animPlaying && !animPaused) {
                // 暂停
                animPaused = true;
                animPlaying = false;
                if (animFrameId) { cancelAnimationFrame(animFrameId); animFrameId = null; }
                const elapsed = performance.now() - animStartTime;
                animPausedAt = Math.min(elapsed / 6000, 1);
                if (btn) btn.innerHTML = '▶ 继续';
            } else if (animPaused) {
                // 继续
                animPlaying = true;
                animPaused = false;
                animStartTime = null;
                animFrameId = requestAnimationFrame(animateFrame);
                if (btn) btn.innerHTML = '⏸ 暂停';
            } else {
                // 重播
                if (polylineLayer) { mapInstance.removeLayer(polylineLayer); polylineLayer = null; }
                animGhostLine = L.polyline(animAllPoints, {
                    color: '#ffffff', weight: 2, opacity: 0.2, dashArray: '6,8'
                }).addTo(mapInstance);
                animPausedAt = 0;
                if (btn) btn.innerHTML = '⏸ 暂停';
                startTrackAnimation();
            }
        }

        function closeMapPreview() {
            const modal = document.getElementById('mapPreviewModal');
            if (modal) modal.classList.remove('active');
            clearAnimation();
        }

        // --- Push Groups Logic ---
        function editPushGroup(id, name, qq, type, userIds) {
            document.getElementById('pushGroupModalTitle').innerText = '编辑推送组';
            document.getElementById('pg_id').value = id;
            document.getElementById('pg_name').value = name;
            document.getElementById('pg_qq_number').value = qq;
            
            const ms = ModernSelect.instances.get('pg_notify_type_modern');
            if (ms) ms.setValue(type);
            else document.getElementById('pg_qq_notify_type').value = type;
            
            document.querySelectorAll('.pg-group-user-cb').forEach(cb => {
                cb.checked = userIds && userIds.includes(parseInt(cb.value));
            });

            openModal('pushGroupModal');
        }

        async function deletePushGroup(id) {
            showConfirmModal('删除推送组', '确定要删除此推送组吗？绑定该组的账号将不再收到推送。', async () => {
                const rs = await fetch(`/api/push_groups/${id}`, { method: 'DELETE' });
                const json = await rs.json();
                if(json.success) location.reload();
                else showToast(json.msg || '删除失败', 'error');
            });
        }

        async function submitPushGroup(e) {
            e.preventDefault();
            const id = document.getElementById('pg_id').value;
            
            const checkedUsers = [];
            document.querySelectorAll('.pg-group-user-cb:checked').forEach(cb => {
                checkedUsers.push(parseInt(cb.value));
            });

            const data = {
                name: document.getElementById('pg_name').value,
                qq_number: document.getElementById('pg_qq_number').value,
                qq_notify_type: document.getElementById('pg_qq_notify_type').value,
                user_ids: checkedUsers
            };
            const method = id ? 'PUT' : 'POST';
            const url = id ? `/api/push_groups/${id}` : '/api/push_groups';
            const rs = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const json = await rs.json();
            if (json.success) {
                location.reload();
            } else {
                showToast(json.msg || '保存失败', 'error');
            }
        }

        async function submitAddUser(e) {
            e.preventDefault();
            const form = e.target;
            const formData = new FormData(form);
            try {
                const res = await fetch('/users/add', {
                    method: 'POST',
                    body: formData
                });
                const result = await res.json();
                if (result.success) {
                    location.reload();
                } else {
                    showAlert(result.message);
                }
            } catch (err) {
                showAlert('网络异常: ' + err);
            }
        }

        async function submitEditUser(e) {
            e.preventDefault();
            const form = e.target;
            const formData = new FormData(form);
            try {
                const res = await fetch('/users/edit', {
                    method: 'POST',
                    body: formData
                });
                const result = await res.json();
                if (result.success) {
                    location.reload();
                } else {
                    showAlert(result.message);
                }
            } catch (err) {
                showAlert('网络异常: ' + err);
            }
        }

        // Initialize display logic for edit user popups dynamically
        (() => {
            window.editUser = async function(id) {
                try {
                    const response = await fetch(`/api/users/${id}`);
                    const user = await response.json();

                    document.getElementById('edit_user_id').value = user.id;
                    document.getElementById('edit_username').value = user.username;
                    document.getElementById('edit_yun_username').value = user.yun_username;
                    document.getElementById('edit_yun_password').value = '';

                    const ms = typeof ModernSelect !== 'undefined' && ModernSelect.instances ? ModernSelect.instances.get('edit_school_select_modern') : null;
                    if (ms) {
                        ms.setValue(user.school_id || '');
                    } else {
                        document.getElementById('edit_school_id').value = user.school_id || '';
                    }

                    openModal('editUserModal');
                } catch (error) {
                    showAlert('获取用户信息失败: ' + error);
                }
            };
        })();

        async function testPushGroup(target, notifyType) {
            showToast('正在发送测试消息...', 'info');
            try {
                const rs = await fetch('/api/push_groups/test', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ qq_number: target, qq_notify_type: notifyType })
                });
                const json = await rs.json();
                if (json.success) {
                    showToast('测试消息发送成功！', 'success');
                } else {
                    showToast('发送失败: ' + (json.msg || '未知错误'), 'error');
                }
            } catch (e) {
                showToast('网络异常: ' + e, 'error');
            }
        }
}
