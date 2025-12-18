function formatBytes(bytes,decimals) {
   if(bytes == 0) return '0 کیلوبایت';
   var k = 1024,
       dm = decimals || 2,
       sizes = ['بایت', 'کیلوبایت', 'مگابایت', 'گیگابایت'],
       i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), 3);
   return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function adjustWidth(element) {
    const selectedOption = element.options[element.selectedIndex].text;
    const tempElement = document.createElement('span');
    tempElement.style.visibility = 'hidden';
    tempElement.style.whiteSpace = 'nowrap';
    tempElement.style.font = window.getComputedStyle(element).font;
    tempElement.innerText = selectedOption;
    
    document.body.appendChild(tempElement);
    const width = tempElement.offsetWidth + 16;
    document.body.removeChild(tempElement);

    element.style.width = width + 'px';
}

function check_traffic()
{
  pywebview.api.get_rx().then(function(rx) {
    $("#used_traffic").text(formatBytes(rx));
  });
}

window.addEventListener('pywebviewready', function() 
{
  document.querySelector("html").style.zoom = window.outerHeight / (document.querySelector("html").offsetHeight + 30);
  $('body').css('visibility', 'visible');

  dns_select = document.getElementById('dns_select');
  update_select = document.getElementById('update_select');
  autoconnect_switch = document.getElementById('autoconnect_switch');

  pywebview.api.get_preferences().then(function(preferences) {
    pywebview.api.get_anti_sanction_data().then(function(dns_servers) {
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
      for (var index in dns_servers)
      {
        option = document.createElement('option');
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
      } else if (preferences['dns_server'])
      {
        dns_select.value = preferences['dns_server']
        pywebview.api.change_anti_sanction(preferences['dns_server']);
        
        // Check if selected DNS is custom and show edit button
        const selectedOption = dns_select.options[dns_select.selectedIndex];
        if (selectedOption && selectedOption.dataset.isCustom === 'true') {
          document.getElementById('edit_dns_button').style.display = 'block';
        }
      }
      if (preferences['update'])
      {
        update_select.value = preferences['update']
      }
      adjustWidth(dns_select);
      adjustWidth(update_select);
    });
    if (preferences['auto_connect'])
    {
      autoconnect_switch.checked = true
    }
  });
  

  autostart_switch = document.getElementById('autostart_switch');
  pywebview.api.is_in_startup().then(function(is_in_startup) {
    if (is_in_startup)
    {
      autostart_switch.checked = true
    }
  });

  check_traffic();
  check_traffic = setInterval(check_traffic, 2001);

  status_translation = {"active": "فعال", "expired": "منقضی شده"};
  pywebview.api.get_user_data().then(function(user_data) {
    $("#subscription_id").text(user_data["subscription_id"]);
    $("#subscription_status").text(status_translation[user_data["status"]] || "غیر فعال");
    if (user_data["end"])
    {
      now = new Date();
      then = new Date(user_data["end"])
      days = Math.ceil((then.getTime() - now.getTime())/86400000)
      $("#remaining_days").text(days + " روز");
    }
    else
    {
      $("#remaining_days").hide();
    }
  });

  pywebview.api.get_version().then(function(version) {
    $("#version").text("v" + version);
  });

  $('#close_button').click(function(){
    pywebview.api.close();
  });

  $('#minimize_button').click(function(){
    pywebview.api.minimize();
  });

  // Store the previous DNS selection
  let previousDnsValue = dns_select.value;
  
  $('#dns_select').change(function(){
    // Check if "Add New" option was selected
    if (this.value === '__add_new__') {
      // Reset to previous value
      this.value = previousDnsValue;
      adjustWidth(this);
      
      // Open modal for adding new DNS
      document.getElementById('modal_title').textContent = 'افزودن سرور DNS سفارشی';
      document.getElementById('dns_edit_mode').value = 'add';
      document.getElementById('dns_old_name').value = '';
      document.getElementById('dns_persian_name').value = '';
      document.getElementById('dns_primary_ip').value = '';
      document.getElementById('dns_delete_btn').style.display = 'none';
      hideMessage();
      document.getElementById('dns_modal').style.display = 'block';
      return;
    }
    
    previousDnsValue = this.value;
    pywebview.api.change_anti_sanction(this.value);
    adjustWidth(this);
    
    // Show/hide edit button based on whether custom DNS is selected
    const selectedOption = this.options[this.selectedIndex];
    const editBtn = document.getElementById('edit_dns_button');
    if (selectedOption && selectedOption.dataset.isCustom === 'true') {
      editBtn.style.display = 'block';
    } else {
      editBtn.style.display = 'none';
    }
  });

  $('#update_select').change(function(){
    pywebview.api.change_update_option(this.value);
    adjustWidth(this);
  })

  $('#autostart_switch').change(function(){
    if (this.checked)
    {
      pywebview.api.add_to_startup();
    }
    else
    {
      pywebview.api.remove_from_startup();
    }
  });

  $('#autoconnect_switch').change(function(){
      pywebview.api.toggle_autoconnect();
  });

  $('#power_button').click(function() {
    if (!$(this).hasClass("disabled"))
    {
      $(this).addClass("disabled");
      pywebview.api.toggle_proxy().then(function(local_ip) {
        if (local_ip)
        {
          if (!$('#power_button').hasClass('on'))
          {
            $('#power_button').addClass('on');
          }
          $("#local_ip").text(local_ip);
          if ($('#dns_select').val() == "automatic")
          {
            pywebview.api.test_anti_sanction();
          }
        }
        else
        {
          $("#local_ip").text("");
          if ($('#power_button').hasClass('on'))
          {
            $('#power_button').removeClass('on');
          }
        }
        $('#power_button').removeClass("disabled")
      });
    }
  });

  // Modal functions
  const modal = document.getElementById('dns_modal');
  const editDnsBtn = document.getElementById('edit_dns_button');
  const modalClose = document.getElementById('modal_close');
  const cancelBtn = document.getElementById('dns_cancel_btn');
  const saveBtn = document.getElementById('dns_save_btn');
  const deleteBtn = document.getElementById('dns_delete_btn');
  
  // Open modal for editing
  editDnsBtn.addEventListener('click', function() {
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
        modal.style.display = 'block';
      }
    }
  });
  
  // Close modal
  function closeModal() {
    modal.style.display = 'none';
    hideMessage();
  }
  modalClose.addEventListener('click', closeModal);
  cancelBtn.addEventListener('click', closeModal);
  
  // Close modal when clicking outside
  window.addEventListener('click', function(event) {
    if (event.target == modal) {
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
  saveBtn.addEventListener('click', function() {
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
      pywebview.api.add_custom_dns(persianName, primaryIp).then(function(result) {
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
      pywebview.api.edit_custom_dns(oldName, persianName, primaryIp).then(function(result) {
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
  deleteBtn.addEventListener('click', function() {
    if (confirm('آیا مطمئن هستید که می‌خواهید این سرور DNS را حذف کنید?')) {
      const dnsName = document.getElementById('dns_old_name').value;
      pywebview.api.delete_custom_dns(dnsName).then(function(result) {
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

})


