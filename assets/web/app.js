function formatBytes(bytes,decimals) {
   if(bytes == 0) return '0 کیلوبایت';
   var k = 1024,
       dm = decimals || 2,
       sizes = ['بایت', 'کیلوبایت', 'مگابایت', 'گیگابایت'],
       i = Math.floor(Math.log(bytes) / Math.log(k));
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

function check_proxy_status()
{
  pywebview.api.check_proxy_status().then(function(running) {
    if (running)
    {
      if (!$('.power-button').hasClass('on'))
      {
        $('.power-button').addClass('on');
      }
    }
    else
    {
      if ($('.power-button').hasClass('on'))
      {
        $('.power-button').removeClass('on');
        $("#local_ip").text("");
      }
      if ($('#autoconnect_switch').is(':checked'))
      {
        $('.power-button').click();
      }
    }
  });
}

function check_traffic()
{
  pywebview.api.get_rx().then(function(rx) {
    $("#used_traffic").text(formatBytes(rx));
  });
}

window.addEventListener('pywebviewready', function() 
{
  document.querySelector("html").style.zoom = window.outerHeight / (document.querySelector("html").offsetHeight + 10);
  $('body').css('visibility', 'visible');

  dns_select = document.getElementById('dns_select');
  autoconnect_switch = document.getElementById('autoconnect_switch');

  pywebview.api.load_preferences().then(function(preferences) {
    pywebview.api.get_anti_sanction_data().then(function(dns_servers) {
      for (var index in dns_servers)
      {
        option = document.createElement('option');
        option.value = dns_servers[index]["name"];
        option.innerHTML = dns_servers[index]["persian_name"];
        dns_select.appendChild(option);
      }
      if (preferences['dns_server'])
      {
        dns_select.value = preferences['dns_server']
        pywebview.api.change_anti_sanction(preferences['dns_server']);
      }
      adjustWidth(dns_select);
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

  $('#dns_select').change(function(){
    pywebview.api.change_anti_sanction(this.value);
    adjustWidth(this);
  });

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

  check_interval = setInterval(check_proxy_status, 1001);
  $('.power-button').click(function() {
    pywebview.api.toggle_proxy().then(function(local_ip) {
      $("#local_ip").text(local_ip);
      if ($('#dns_select').val() == "automatic")
      {
        pywebview.api.test_anti_sanction();
      }
    });
  });

})


