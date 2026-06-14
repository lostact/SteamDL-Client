function formatBytes(bytes, decimals) {
  if (bytes == 0) return '0 کیلوبایت';
  var k = 1024,
    dm = decimals || 2,
    sizes = ['بایت', 'کیلوبایت', 'مگابایت', 'گیگابایت'],
    i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), 3);
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function showToast(message) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 3000);
}

function check_traffic() {
  pywebview.api.get_rx().then(function (rx) {
    $("#used_traffic").text(formatBytes(rx));
  });
}

window.addEventListener('pywebviewready', function () {
  $('body').css('visibility', 'visible');

  const update_select = document.getElementById('update_select');
  const autoconnect_switch = document.getElementById('autoconnect_switch');
  const autostart_switch = document.getElementById('autostart_switch');
  const power_button = document.getElementById('power_button');
  const statusText = document.getElementById('statusText');
  const darkModeBtn = document.getElementById('darkModeBtn');

  // Dark Mode Logic - Make dark mode the default
  if (localStorage.getItem('darkMode') !== 'disabled') {
    document.body.classList.add('dark');
  }

  darkModeBtn.addEventListener('click', () => {
    document.body.classList.toggle('dark');
    if (document.body.classList.contains('dark')) {
      localStorage.setItem('darkMode', 'enabled');
    } else {
      localStorage.setItem('darkMode', 'disabled');
    }
  });

  pywebview.api.get_preferences().then(function (preferences) {
    if (preferences['update']) {
      update_select.value = preferences['update'];
    }
    if (preferences['auto_connect']) {
      autoconnect_switch.checked = true;
    }
  });

  pywebview.api.is_in_startup().then(function (is_in_startup) {
    if (is_in_startup) {
      autostart_switch.checked = true;
    }
  });

  check_traffic();
  setInterval(check_traffic, 500);

  const status_translation = { "active": "اشتراک فعال", "expired": "اشتراک منقضی شده" };
  pywebview.api.get_user_data().then(function (user_data) {
    $("#subscription_id").text("#" + user_data["subscription_id"]);
    const status = user_data["status"];
    const statusElem = $("#subscription_status");
    statusElem.text(status_translation[status] || "غیر فعال");
    
    if (status === "active") {
      statusElem.removeClass("is-off").addClass("is-on");
    } else {
      statusElem.removeClass("is-on").addClass("is-off");
    }

    if (user_data["end"]) {
      const now = new Date();
      const then = new Date(user_data["end"])
      const days = Math.ceil((then.getTime() - now.getTime()) / 86400000)
      $("#remaining_days").text(days + " روز");
    }
    else {
      $("#remaining_days").text("---");
    }
  });

  pywebview.api.get_version().then(function (version) {
    $("#version").text("v" + version);
  });

  $('#close_button').click(function () {
    pywebview.api.close();
  });

  $('#minimize_button').click(function () {
    pywebview.api.minimize();
  });

  $('#update_select').change(function () {
    pywebview.api.change_update_option(this.value);
  });

  $('#autostart_switch').change(function () {
    if (this.checked) {
      pywebview.api.add_to_startup();
    }
    else {
      pywebview.api.remove_from_startup();
    }
  });

  $('#autoconnect_switch').change(function () {
    pywebview.api.toggle_autoconnect();
  });

  $('#power_button').click(function () {
    if (!$(this).hasClass("disabled")) {
      $(this).addClass("disabled");
      // Set status to changing (yellow) - only change color, keep text
      statusText.className = "status-changing";
      
      pywebview.api.toggle_proxy().then(function (result) {
        if (result) {
          if (!$('#power_button').hasClass('on')) {
            $('#power_button').addClass('on');
          }
          statusText.textContent = "روشن";
          statusText.className = "status-on";
        }
        else {
          statusText.textContent = "خاموش";
          statusText.className = "status-off";
          if ($('#power_button').hasClass('on')) {
            $('#power_button').removeClass('on');
          }
        }
        $('#power_button').removeClass("disabled");
      });
    }
  });

  // Help Modal Logic
  const helpBtn = document.getElementById('helpBtn');
  const helpOverlay = document.getElementById('helpOverlay');
  const closeHelpX = document.getElementById('closeHelpX');
  const closeHelpBtn = document.getElementById('closeHelpBtn');

  helpBtn.addEventListener('click', () => {
    helpOverlay.classList.add('show');
  });

  const closeHelp = () => {
    helpOverlay.classList.remove('show');
  };

  closeHelpX.addEventListener('click', closeHelp);
  closeHelpBtn.addEventListener('click', closeHelp);

  window.addEventListener('click', (event) => {
    if (event.target == helpOverlay) {
      closeHelp();
    }
  });

});
