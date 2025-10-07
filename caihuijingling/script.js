// 导航栏按钮逻辑
const loginBtn = document.getElementById("loginBtn");
const registerBtn = document.getElementById("registerBtn");
const logoutBtn = document.getElementById("logoutBtn");
const welcomeMsg = document.getElementById("welcomeMsg");
const loginPrompt = document.getElementById("loginPrompt");

function checkLogin() { return localStorage.getItem("loggedIn") === "true"; }
function getUsername() { return localStorage.getItem("username") || "用户"; }

function updateNavbar() {
    if (checkLogin()) {
        loginBtn.style.display = "none";
        registerBtn.style.display = "none";
        logoutBtn.style.display = "inline-block";
        welcomeMsg.style.display = "inline";
        welcomeMsg.textContent = `欢迎回来，${getUsername()}！`;
        loginPrompt.classList.add("hidden");
    } else {
        loginBtn.style.display = "inline-block";
        registerBtn.style.display = "inline-block";
        logoutBtn.style.display = "none";
        welcomeMsg.style.display = "none";
        loginPrompt.classList.remove("hidden");
    }
}

loginBtn.onclick = () => { window.location.href = "login.html"; };
registerBtn.onclick = () => { window.location.href = "register.html"; };
logoutBtn.onclick = () => {
    if (confirm("确定要退出登录吗？")) {
        localStorage.removeItem("loggedIn");
        localStorage.removeItem("username");
        updateNavbar();
        alert("已成功退出登录");
    }
};

updateNavbar();

function requireLogin(action) {
    if (!checkLogin()) {
        if (confirm("请先登录才能使用此功能！是否前往登录页面？")) {
            window.location.href = "login.html";
        }
        return false;
    }
    action();
}

function showError(message) { alert("❌ " + message); }
function showSuccess(message) { console.log("✅ " + message); }

// 左边：线稿上色
document.getElementById('btn-colorize').onclick = () => {
    requireLogin(async () => {
        const imageFile = document.getElementById('image-colorize').files[0];
        const prompt = document.getElementById('prompt').value.trim();
        const btn = document.getElementById('btn-colorize');
        const loading = document.getElementById('loading-colorize');
        const resultImg = document.getElementById('result-colorize');
        const downloadLink = document.getElementById('download-colorize');

        if (!imageFile) { showError("请选择线稿图片"); return; }
        if (!prompt) { showError("请输入上色描述"); return; }

        btn.disabled = true; loading.style.display = 'block';
        resultImg.style.display = 'none'; downloadLink.style.display = 'none';

        const formData = new FormData();
        formData.append("prompt", prompt);
        formData.append("image", imageFile);

        try {
            const res = await fetch("http://127.0.0.1:8000/colorize", { method: "POST", body: formData });
            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.detail || errorData.error || "上色失败");
            }
            const data = await res.json();
            resultImg.src = data.image_url; resultImg.style.display = 'block';
            downloadLink.href = data.image_url; downloadLink.style.display = 'inline-block';
            showSuccess("线稿上色完成！");
        } catch (err) { showError("上色失败: " + err.message); }
        finally { btn.disabled = false; loading.style.display = 'none'; }
    });
};

// 中间：彩色图转线稿
document.getElementById('btn-sketch').onclick = () => {
    requireLogin(async () => {
        const imageFile = document.getElementById('image-sketch').files[0];
        const btn = document.getElementById('btn-sketch');
        const loading = document.getElementById('loading-sketch');
        const resultImg = document.getElementById('result-sketch');
        const downloadLink = document.getElementById('download-sketch');

        // 读取用户选择的提取方式
        const method = document.querySelector('input[name="sketch-method"]:checked').value;

        if (!imageFile) {
            showError("请选择彩色图片");
            return;
        }

        // 显示加载动画
        btn.disabled = true;
        loading.style.display = 'block';
        resultImg.style.display = 'none';
        downloadLink.style.display = 'none';

        const formData = new FormData();
        formData.append("image", imageFile);
        formData.append("method", method);  // 传给后端

        try {
            const res = await fetch("http://127.0.0.1:8000/to_sketch", {
                method: "POST",
                body: formData
            });

            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.detail || errorData.error || "生成线稿失败");
            }

            const data = await res.json();
            resultImg.src = data.image_url;
            resultImg.style.display = 'block';
            downloadLink.href = data.image_url;
            downloadLink.style.display = 'inline-block';
            showSuccess("线稿生成完成！");
        } catch (err) {
            showError("生成线稿失败: " + err.message);
        } finally {
            btn.disabled = false;
            loading.style.display = 'none';
        }
    });
};



// 右边：Kimi 角色描述
document.getElementById('btn-kimi').onclick = () => {
    requireLogin(async () => {
        const imageFile = document.getElementById('image-kimi').files[0];
        const btn = document.getElementById('btn-kimi');
        const loading = document.getElementById('loading-kimi');
        const resultBox = document.getElementById('result-kimi');

        if (!imageFile) { showError("请选择图片"); return; }

        btn.disabled = true; loading.style.display = 'block'; resultBox.style.display = 'none';

        const formData = new FormData();
        formData.append("image", imageFile);

        try {
            const res = await fetch("http://127.0.0.1:8000/kimi_describe", { method: "POST", body: formData });
            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.detail || errorData.error || "生成描述失败");
            }
            const data = await res.json();
            if (data.description) {
                resultBox.innerText = data.description; resultBox.style.display = 'block';
                showSuccess("角色描述生成完成！");
            } else { throw new Error("未获取到描述内容"); }
        } catch (err) { showError("生成描述失败: " + err.message); }
        finally { btn.disabled = false; loading.style.display = 'none'; }
    });
};
// 通用预览函数
function previewImage(inputId, previewId) {
    const input = document.getElementById(inputId);
    const preview = document.getElementById(previewId);

    input.addEventListener('change', function () {
        const file = this.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function (e) {
                preview.src = e.target.result;
                preview.style.display = 'block';
            };
            reader.readAsDataURL(file);
        } else {
            preview.style.display = 'none';
        }
    });
}

// 三个功能区绑定
previewImage("image-colorize", "preview-colorize");
previewImage("image-sketch", "preview-sketch");
previewImage("image-kimi", "preview-kimi");
