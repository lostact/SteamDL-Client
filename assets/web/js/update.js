// JavaScript for update.html
function updateProgress(percent) {
    document.getElementById('progress-bar-inner').style.width = percent + '%';
    document.getElementById('progress-text').innerText = percent + '%';
}

document.getElementById('close_button').addEventListener('click', function() {
    pywebview.api.close();
});

document.getElementById('minimize_button').addEventListener('click', function() {
    pywebview.api.minimize();
});
