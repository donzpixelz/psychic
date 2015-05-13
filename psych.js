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

function sendfacebook(data) {
    $.ajax({
	method: "GET",
	url: "index.cgi?facebook=on",
	data: {reply:data}
    })
    .done(function( msg ) {
    //  alert(msg);
    //  $('span#conversation').append(msg); //temporary - don't usually want to display the reply to this.
    });
}

$(document).ready(function() {
 replymsg();
 $('button#reply').click(function() {replymsg();});
});

$(document).ready(function() {
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
				    sendfacebook(data);
	    		});
	  	}
	}
//see https://developers.facebook.com/docs/reference/fql/permissions
//see https://developers.facebook.com/docs/graph-api/reference/user

	FB.getLoginStatus(function(response) {
		// Check login status on load, and if the user is
		// already logged in, go directly to the welcome message.
		if (response.status == 'connected') {
			onLogin(response);
		} else {
	    	// Otherwise, show Login dialog first.
		  	FB.login(function(response) {
		 		onLogin(response);
		 	}, {scope: 'user_friends, email, user_birthday, user_about_me, user_likes, user_photos'});
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
});
