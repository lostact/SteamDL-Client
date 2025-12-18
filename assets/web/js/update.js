// JavaScript for update.html
function updateProgress(percent) {
    document.getElementById('progress-bar-inner').style.width = percent + '%';
    document.getElementById('progress-text').innerText = percent + '%';
}
