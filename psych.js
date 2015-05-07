function replymsg() {
    $.ajax({
	method: "GET",
	url: "index.cgi?ajax=on",
	data: {reply:$('textarea').val()}
    })
    .done(function( msg ) {
      $('span#conversation').append(msg);
      if (msg.indexOf("<!--query-->")>=0)
      {
        replymsg(); //the server wants to say something else!
      }
    });
}

$(document).ready(function() {
 replymsg();
 $('button#reply').click(function() {replymsg();});
});


/*--------Facebook connection code------*/
window.fbAsyncInit = function() {
	FB.init({
		appId      : '410527355776874',
		xfbml      : true,
		version    : 'v2.3'
   	});

	function onLogin(response) {
		if (response.status == 'connected') {
			FB.api('/me?fields=first_name', function(data) {
				var welcomeBlock = document.getElementById('fb-welcome');
				welcomeBlock.innerHTML = 'Hello, ' + data.first_name + '!';
	    		});
			FB.api('/me', function(data) {
				console.log(data);
	    		});
	  	}
	}

	FB.getLoginStatus(function(response) {
		// Check login status on load, and if the user is
		// already logged in, go directly to the welcome message.
		if (response.status == 'connected') {
			onLogin(response);
		} else {
	    	// Otherwise, show Login dialog first.
		  	FB.login(function(response) {
		 		onLogin(response);
		 	}, {scope: 'user_friends, email'});
		}
	});
  };

  (function(d, s, id){
     var js, fjs = d.getElementsByTagName(s)[0];
     if (d.getElementById(id)) {return;}
     js = d.createElement(s); js.id = id;
     js.src = "//connect.facebook.net/en_US/sdk.js";
     fjs.parentNode.insertBefore(js, fjs);
   }(document, 'script', 'facebook-jssdk'));
/*--------------------------------------*/
