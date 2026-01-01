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
  // Adjust zoom for different screen sizes if needed
  // document.querySelector("html").style.zoom = window.outerHeight / (document.querySelector("html").offsetHeight + 30);
  $('body').css('visibility', 'visible');

  const dns_select = document.getElementById('dns_select');
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
    pywebview.api.get_anti_sanction_data().then(function (dns_servers) {
      // Store globally
      window.dnsServers = dns_servers;

      // Clear existing options except the "Add New" option
      const addNewOption = dns_select.querySelector('option[value="__add_new__"]');
      dns_select.innerHTML = '';

      // Add automatic option first
      const autoOption = document.createElement('option');
      autoOption.value = 'automatic';
      autoOption.innerHTML = 'خودکار';
      dns_select.appendChild(autoOption);

      // Add DNS servers
      for (var index in dns_servers) {
        const option = document.createElement('option');
        option.value = dns_servers[index]["name"];
        option.innerHTML = dns_servers[index]["persian_name"];

        // Mark custom DNS
        if (dns_servers[index]["is_custom"]) {
          option.className = "custom-dns";
          option.dataset.isCustom = "true";
        }

        dns_select.appendChild(option);
      }

      // Add "Add New" option at the end
      dns_select.appendChild(addNewOption);

      // Check if we need to select a newly added DNS
      const selectDns = localStorage.getItem('select_dns_after_reload');
      if (selectDns) {
        localStorage.removeItem('select_dns_after_reload');
        dns_select.value = selectDns;
        pywebview.api.change_anti_sanction(selectDns);

        // Check if it's custom and show edit button
        const selectedOption = dns_select.options[dns_select.selectedIndex];
        if (selectedOption && selectedOption.dataset.isCustom === 'true') {
          document.getElementById('edit_dns_button').style.display = 'block';
        }
      } else if (preferences['dns_server']) {
        dns_select.value = preferences['dns_server']
        pywebview.api.change_anti_sanction(preferences['dns_server']);

        // Check if selected DNS is custom and show edit button
        const selectedOption = dns_select.options[dns_select.selectedIndex];
        if (selectedOption && selectedOption.dataset.isCustom === 'true') {
          document.getElementById('edit_dns_button').style.display = 'block';
        }
      }
      if (preferences['update']) {
        update_select.value = preferences['update']
      }
    });
    if (preferences['auto_connect']) {
      autoconnect_switch.checked = true
    }
  });


  pywebview.api.is_in_startup().then(function (is_in_startup) {
    if (is_in_startup) {
      autostart_switch.checked = true
    }
  });

  check_traffic();
  setInterval(check_traffic, 2001);

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

  // Store the previous DNS selection
  let previousDnsValue = dns_select.value;

  $('#dns_select').change(function () {
    // Check if "Add New" option was selected
    if (this.value === '__add_new__') {
      // Reset to previous value
      this.value = previousDnsValue;

      // Open modal for adding new DNS
      document.getElementById('modal_title').textContent = 'افزودن سرور DNS سفارشی';
      document.getElementById('dns_edit_mode').value = 'add';
      document.getElementById('dns_old_name').value = '';
      document.getElementById('dns_persian_name').value = '';
      document.getElementById('dns_primary_ip').value = '';
      document.getElementById('dns_delete_btn').style.display = 'none';
      hideMessage();
      document.getElementById('dns_modal').classList.add('show');
      return;
    }

    previousDnsValue = this.value;
    pywebview.api.change_anti_sanction(this.value);

    // Show/hide edit button based on whether custom DNS is selected
    const selectedOption = this.options[this.selectedIndex];
    const editBtn = document.getElementById('edit_dns_button');
    if (selectedOption && selectedOption.dataset.isCustom === 'true') {
      editBtn.style.display = 'block';
    } else {
      editBtn.style.display = 'none';
    }
  });

  $('#update_select').change(function () {
    pywebview.api.change_update_option(this.value);
  })

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
      
      pywebview.api.toggle_proxy().then(function (local_ip) {
        if (local_ip) {
          if (!$('#power_button').hasClass('on')) {
            $('#power_button').addClass('on');
          }
          $("#local_ip").text(local_ip);
          statusText.textContent = "روشن";
          statusText.className = "status-on";
          if ($('#dns_select').val() == "automatic") {
            pywebview.api.test_anti_sanction();
          }
        }
        else {
          $("#local_ip").text("---");
          statusText.textContent = "خاموش";
          statusText.className = "status-off";
          if ($('#power_button').hasClass('on')) {
            $('#power_button').removeClass('on');
          }
        }
        $('#power_button').removeClass("disabled")
      });
    }
  });

  // Modal functions
  const dnsModal = document.getElementById('dns_modal');
  const editDnsBtn = document.getElementById('edit_dns_button');
  const modalClose = document.getElementById('modal_close');
  const cancelBtn = document.getElementById('dns_cancel_btn');
  const saveBtn = document.getElementById('dns_save_btn');
  const deleteBtn = document.getElementById('dns_delete_btn');

  // Open modal for editing
  editDnsBtn.addEventListener('click', function () {
    const selectedOption = dns_select.options[dns_select.selectedIndex];
    if (selectedOption && selectedOption.dataset.isCustom === 'true') {
      const selectedDnsName = selectedOption.value;
      const dnsData = window.dnsServers.find(dns => dns.name === selectedDnsName);

      if (dnsData) {
        document.getElementById('modal_title').textContent = 'ویرایش سرور DNS';
        document.getElementById('dns_edit_mode').value = 'edit';
        document.getElementById('dns_old_name').value = dnsData.name;
        document.getElementById('dns_persian_name').value = dnsData.persian_name;
        document.getElementById('dns_primary_ip').value = dnsData.ip;
        deleteBtn.style.display = 'block';
        hideMessage();
        dnsModal.classList.add('show');
      }
    }
  });

  // Close modal
  function closeModal() {
    dnsModal.classList.remove('show');
    hideMessage();
  }
  modalClose.addEventListener('click', closeModal);
  cancelBtn.addEventListener('click', closeModal);

  // Close modal when clicking outside
  window.addEventListener('click', function (event) {
    if (event.target == dnsModal) {
      closeModal();
    }
  });

  // Show/hide message
  function showMessage(text, isSuccess) {
    const messageDiv = document.getElementById('dns_message');
    messageDiv.textContent = text;
    messageDiv.className = 'dns-message ' + (isSuccess ? 'success' : 'error');
    messageDiv.style.display = 'block';
  }

  function hideMessage() {
    const messageDiv = document.getElementById('dns_message');
    messageDiv.style.display = 'none';
  }

  // Save DNS
  saveBtn.addEventListener('click', function () {
    const mode = document.getElementById('dns_edit_mode').value;
    const persianName = document.getElementById('dns_persian_name').value.trim();
    const primaryIp = document.getElementById('dns_primary_ip').value.trim();

    // Validation
    if (!persianName || !primaryIp) {
      showMessage('لطفا همه فیلدها را پر کنید', false);
      return;
    }

    saveBtn.disabled = true;
    saveBtn.textContent = 'در حال ذخیره...';

    if (mode === 'add') {
      pywebview.api.add_custom_dns(persianName, primaryIp).then(function (result) {
        saveBtn.disabled = false;
        saveBtn.textContent = 'ذخیره';

        const [success, message, dnsName] = result;
        if (success) {
          // Save the new DNS name to select it after reload
          if (dnsName) {
            localStorage.setItem('select_dns_after_reload', dnsName);
          }
          closeModal();
          location.reload();
        } else {
          showMessage(message, false);
        }
      });
    } else {
      const oldName = document.getElementById('dns_old_name').value;
      pywebview.api.edit_custom_dns(oldName, persianName, primaryIp).then(function (result) {
        saveBtn.disabled = false;
        saveBtn.textContent = 'ذخیره';

        const [success, message] = result;
        if (success) {
          closeModal();
          location.reload();
        } else {
          showMessage(message, false);
        }
      });
    }
  });

  // Delete DNS
  deleteBtn.addEventListener('click', function () {
    const dnsName = document.getElementById('dns_old_name').value;
    pywebview.api.delete_custom_dns(dnsName).then(function (result) {
      const [success, message] = result;
      if (success) {
        closeModal();
        location.reload();
      } else {
        showMessage(message, false);
      }
    });
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

})



