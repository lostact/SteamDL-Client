// JavaScript for form.html
$('#submit_button').click(function(){
  token = $('#token_input').val();
  pywebview.api.submit_token(token)
});

$('#paste_button').click(function(){
  navigator.clipboard.readText()
  .then(text => { $('#token_input').val(text); })
  .catch(err => {
      console.error('Failed to read clipboard contents: ', err);
  });
});

$('#close_button').click(function(){
  pywebview.api.close();
});

$('#minimize_button').click(function(){
  pywebview.api.minimize();
});

function toggle(element)
{ 
  if (element.style.display === 'none') 
  { 
      element.style.display = "block"; 
  } 
  else 
  { 
      element.style.display = "none" 
  } 
}
