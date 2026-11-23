/**
 * TruthLens AI - Client Interactions & UI Logic
 */

document.addEventListener("DOMContentLoaded", () => {
    // -------------------------------------------------------------
    // 1. Toast Notification System & Flash Messages
    // -------------------------------------------------------------
    const toastContainer = document.getElementById("toastContainer");

    window.showToast = function (message, type = "info", duration = 4000) {
        if (!toastContainer) return;

        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;

        const iconSvg =
            type === "success"
                ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>'
                : type === "error"
                ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>'
                : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>';

        toast.innerHTML = `
            ${iconSvg}
            <span class="toast-message">${message}</span>
            <button class="toast-close" aria-label="Dismiss">&times;</button>
        `;

        toast.querySelector(".toast-close").addEventListener("click", () => {
            toast.remove();
        });

        toastContainer.appendChild(toast);

        setTimeout(() => {
            if (toast.parentElement) {
                toast.style.transition = "opacity 0.3s ease, transform 0.3s ease";
                toast.style.opacity = "0";
                toast.style.transform = "translateX(20px)";
                setTimeout(() => toast.remove(), 300);
            }
        }, duration);
    };

    // Render server-side flashed messages as toasts
    const flashMessagesContainer = document.getElementById("flashMessages");
    if (flashMessagesContainer) {
        flashMessagesContainer.querySelectorAll("span").forEach((span) => {
            const category = span.getAttribute("data-category") || "info";
            const message = span.getAttribute("data-message") || "";
            if (message) {
                const toastType = category === "error" ? "error" : category === "success" ? "success" : "info";
                window.showToast(message, toastType);
            }
        });
    }

    // -------------------------------------------------------------
    // 2. Navigation Mobile Toggle & User Menu Dropdown
    // -------------------------------------------------------------
    const navToggle = document.getElementById("navToggle");
    const navMenu = document.getElementById("navMenu");
    if (navToggle && navMenu) {
        navToggle.addEventListener("click", () => {
            const isOpen = navMenu.classList.toggle("show");
            navToggle.setAttribute("aria-expanded", isOpen);
        });
    }

    const userMenuBtn = document.getElementById("userMenuBtn");
    const userDropdown = document.getElementById("userDropdown");
    if (userMenuBtn && userDropdown) {
        userMenuBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            userDropdown.classList.toggle("show");
            userMenuBtn.setAttribute("aria-expanded", userDropdown.classList.contains("show"));
        });

        document.addEventListener("click", (e) => {
            if (!userDropdown.contains(e.target) && !userMenuBtn.contains(e.target)) {
                userDropdown.classList.remove("show");
                userMenuBtn.setAttribute("aria-expanded", "false");
            }
        });
    }

    // -------------------------------------------------------------
    // 3. Detector Tabs (Text vs URL)
    // -------------------------------------------------------------
    const tabTextBtn = document.getElementById("tabTextBtn");
    const tabUrlBtn = document.getElementById("tabUrlBtn");
    const textPanel = document.getElementById("textPanel");
    const urlPanel = document.getElementById("urlPanel");

    if (tabTextBtn && tabUrlBtn && textPanel && urlPanel) {
        tabTextBtn.addEventListener("click", () => {
            tabTextBtn.classList.add("active");
            tabTextBtn.setAttribute("aria-selected", "true");
            tabUrlBtn.classList.remove("active");
            tabUrlBtn.setAttribute("aria-selected", "false");

            textPanel.style.display = "block";
            urlPanel.style.display = "none";
        });

        tabUrlBtn.addEventListener("click", () => {
            tabUrlBtn.classList.add("active");
            tabUrlBtn.setAttribute("aria-selected", "true");
            tabTextBtn.classList.remove("active");
            tabTextBtn.setAttribute("aria-selected", "false");

            urlPanel.style.display = "block";
            textPanel.style.display = "none";
        });
    }

    // -------------------------------------------------------------
    // 4. Sample Articles & Character Counter
    // -------------------------------------------------------------
    const newsTextarea = document.getElementById("newsTextarea");
    const charCount = document.getElementById("charCount");
    const wordCount = document.getElementById("wordCount");
    const clearTextBtn = document.getElementById("clearTextBtn");
    const clearUrlBtn = document.getElementById("clearUrlBtn");
    const newsUrlInput = document.getElementById("newsUrlInput");

    const sampleRealBtn = document.getElementById("sampleRealBtn");
    const sampleFakeBtn = document.getElementById("sampleFakeBtn");

    function updateCounts() {
        if (!newsTextarea) return;
        const text = newsTextarea.value.trim();
        const chars = newsTextarea.value.length;
        const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
        if (charCount) charCount.textContent = chars;
        if (wordCount) wordCount.textContent = words;
    }

    if (newsTextarea) {
        newsTextarea.addEventListener("input", updateCounts);
        updateCounts();
    }

    if (clearTextBtn && newsTextarea) {
        clearTextBtn.addEventListener("click", () => {
            newsTextarea.value = "";
            updateCounts();
            newsTextarea.focus();
        });
    }

    if (clearUrlBtn && newsUrlInput) {
        clearUrlBtn.addEventListener("click", () => {
            newsUrlInput.value = "";
            newsUrlInput.focus();
        });
    }

    if (sampleRealBtn && newsTextarea) {
        sampleRealBtn.addEventListener("click", () => {
            newsTextarea.value =
                "The World Health Organization confirmed today that widespread immunization campaigns have successfully reduced measles transmission rates across thirty member states following multi-year coordinated trials.";
            updateCounts();
            window.showToast("Loaded sample verified news statement", "info", 2000);
        });
    }

    if (sampleFakeBtn && newsTextarea) {
        sampleFakeBtn.addEventListener("click", () => {
            newsTextarea.value =
                "SHOCKING SECRET DISCOVERY: Ancient leaked government documents reveal hidden alien technology coverup that officials desperately do not want the public to ever read about!";
            updateCounts();
            window.showToast("Loaded sample sensationalist claim", "info", 2000);
        });
    }

    // -------------------------------------------------------------
    // 5. Form Submission & Loading Indicators
    // -------------------------------------------------------------
    document.querySelectorAll(".analysis-form, .auth-form").forEach((form) => {
        form.addEventListener("submit", () => {
            const submitBtn = form.querySelector(".submit-btn") || form.querySelector("button[type='submit']");
            if (submitBtn) {
                const btnText = submitBtn.querySelector(".btn-text");
                const spinner = submitBtn.querySelector(".spinner");

                if (btnText) btnText.textContent = "Analyzing...";
                if (spinner) spinner.style.display = "inline-block";
                submitBtn.disabled = true;
                submitBtn.style.opacity = "0.75";
            }
        });
    });

    // -------------------------------------------------------------
    // 6. Password Strength Meter & Visibility Toggle
    // -------------------------------------------------------------
    const passwordInput = document.getElementById("passwordInput");
    const pwStrengthFill = document.getElementById("pwStrengthFill");
    const pwStrengthText = document.getElementById("pwStrengthText");

    if (passwordInput && pwStrengthFill && pwStrengthText) {
        passwordInput.addEventListener("input", () => {
            const val = passwordInput.value;
            let score = 0;
            if (val.length >= 8) score++;
            if (/[A-Z]/.test(val)) score++;
            if (/[a-z]/.test(val)) score++;
            if (/\d/.test(val)) score++;
            if (/[^A-Za-z0-9]/.test(val)) score++;

            if (val.length === 0) {
                pwStrengthFill.style.width = "0%";
                pwStrengthFill.style.backgroundColor = "transparent";
                pwStrengthText.textContent = "Password must have 8+ characters, uppercase, lowercase, and numbers";
            } else if (score <= 2) {
                pwStrengthFill.style.width = "30%";
                pwStrengthFill.style.backgroundColor = "#ef4444";
                pwStrengthText.textContent = "Weak password: add uppercase letters and digits";
                pwStrengthText.style.color = "#ef4444";
            } else if (score <= 3) {
                pwStrengthFill.style.width = "65%";
                pwStrengthFill.style.backgroundColor = "#f59e0b";
                pwStrengthText.textContent = "Moderate strength: add special symbols";
                pwStrengthText.style.color = "#d97706";
            } else {
                pwStrengthFill.style.width = "100%";
                pwStrengthFill.style.backgroundColor = "#10b981";
                pwStrengthText.textContent = "Strong password!";
                pwStrengthText.style.color = "#10b981";
            }
        });
    }

    const togglePwBtn = document.getElementById("togglePwBtn");
    if (togglePwBtn && passwordInput) {
        togglePwBtn.addEventListener("click", () => {
            const isPassword = passwordInput.getAttribute("type") === "password";
            passwordInput.setAttribute("type", isPassword ? "text" : "password");
            togglePwBtn.style.opacity = isPassword ? "1" : "0.5";
        });
    }

    // -------------------------------------------------------------
    // 7. Interactive Feedback Widget
    // -------------------------------------------------------------
    window.sendFeedback = function (prediction, isCorrect) {
        const statusElem = document.getElementById("feedbackStatus");
        const actionsElem = document.querySelector(".feedback-actions");
        const newsContent = document.querySelector(".article-text p")?.textContent || "";
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";

        if (statusElem) {
            statusElem.style.display = "inline";
            statusElem.textContent = "Recording feedback...";
        }

        fetch("/feedback", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrfToken
            },
            body: JSON.stringify({
                prediction: prediction,
                is_correct: isCorrect,
                news: newsContent
            })
        })
        .then((res) => res.json())
        .then((data) => {
            if (statusElem) {
                statusElem.textContent = "✅ " + (data.message || "Thank you for your feedback!");
            }
            if (actionsElem) {
                actionsElem.style.opacity = "0.5";
                actionsElem.querySelectorAll("button").forEach((btn) => (btn.disabled = true));
            }
            window.showToast("Feedback submitted successfully. Thank you!", "success");
        })
        .catch(() => {
            if (statusElem) {
                statusElem.textContent = "Could not record feedback.";
            }
            window.showToast("Could not submit feedback.", "error");
        });
    };

    // -------------------------------------------------------------
    // 8. Prediction Distribution Chart (Chart.js)
    // -------------------------------------------------------------
    function renderDoughnutChart(canvasId, fakeCountId, realCountId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || typeof Chart === "undefined") return;

        const fakeCount = Number(document.getElementById(fakeCountId)?.textContent || 0);
        const realCount = Number(document.getElementById(realCountId)?.textContent || 0);

        new Chart(canvas, {
            type: "doughnut",
            data: {
                labels: ["Fake News", "Real News"],
                datasets: [
                    {
                        data: [fakeCount, realCount],
                        backgroundColor: ["#ef4444", "#10b981"],
                        borderWidth: 3,
                        borderColor: "#ffffff",
                        hoverOffset: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: {
                            font: { family: "'Inter', sans-serif", size: 12, weight: 600 },
                            padding: 16,
                            usePointStyle: true
                        }
                    }
                },
                cutout: "70%"
            }
        });
    }

    renderDoughnutChart("newsChart", "fakeCount", "realCount");
    renderDoughnutChart("adminNewsChart", "adminFakeCount", "adminRealCount");

    // -------------------------------------------------------------
    // 9. Reusable Prediction Detail Modal
    // -------------------------------------------------------------
    const detailModal = document.getElementById("detailModal");
    const modalCloseBtn = document.getElementById("modalCloseBtn");

    window.openDetailModal = function (prediction, confidence, date, title, url, content) {
        if (!detailModal) return;

        const modalBadge = document.getElementById("modalBadge");
        const modalTitle = document.getElementById("modalTitle");
        const modalConfidence = document.getElementById("modalConfidence");
        const modalDate = document.getElementById("modalDate");
        const modalUrlRow = document.getElementById("modalUrlRow");
        const modalUrlLink = document.getElementById("modalUrlLink");
        const modalContent = document.getElementById("modalContent");

        if (modalBadge) {
            modalBadge.className = `modal-badge badge-${prediction === "FAKE" ? "fake" : "real"}`;
            modalBadge.textContent = prediction === "FAKE" ? "🔴 FAKE" : "🟢 REAL";
        }

        if (modalTitle) modalTitle.textContent = title || "Prediction Record";
        if (modalConfidence) modalConfidence.textContent = `${confidence}%`;
        if (modalDate) modalDate.textContent = date || "N/A";

        if (url && modalUrlRow && modalUrlLink) {
            modalUrlRow.style.display = "block";
            modalUrlLink.href = url;
            modalUrlLink.textContent = url;
        } else if (modalUrlRow) {
            modalUrlRow.style.display = "none";
        }

        if (modalContent) modalContent.textContent = content || "(No content recorded)";

        detailModal.style.display = "flex";
        detailModal.setAttribute("aria-hidden", "false");
    };

    window.closeDetailModal = function () {
        if (!detailModal) return;
        detailModal.style.display = "none";
        detailModal.setAttribute("aria-hidden", "true");
    };

    if (modalCloseBtn) {
        modalCloseBtn.addEventListener("click", window.closeDetailModal);
    }

    if (detailModal) {
        detailModal.addEventListener("click", (e) => {
            if (e.target === detailModal) {
                window.closeDetailModal();
            }
        });
    }

    // -------------------------------------------------------------
    // 10. Admin Sidebar Section Navigation
    // -------------------------------------------------------------
    const sidebarLinks = document.querySelectorAll(".admin-sidebar .sidebar-link[data-section]");
    if (sidebarLinks.length > 0) {
        sidebarLinks.forEach((link) => {
            link.addEventListener("click", (e) => {
                const targetId = link.getAttribute("data-section");
                const targetElem = document.getElementById(targetId);
                if (targetElem) {
                    sidebarLinks.forEach((l) => l.classList.remove("active"));
                    link.classList.add("active");
                    targetElem.scrollIntoView({ behavior: "smooth" });
                }
            });
        });
    }
});
