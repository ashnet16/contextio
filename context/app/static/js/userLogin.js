$(document).ready(function() {

  var loginIsValid = false;

  var animating = false,
      submitPhase1 = 1100,
      submitPhase2 = 400,
      logoutPhase1 = 800,
      $login = $(".login"),
      $app = $(".app");

  function ripple(elem, e) {
    $(".ripple").remove();
    var elTop = elem.offset().top,
        elLeft = elem.offset().left,
        x = e.pageX - elLeft,
        y = e.pageY - elTop;
    var $ripple = $("<div class='ripple'></div>");
    $ripple.css({top: y, left: x});
    elem.append($ripple);
  };

  function userInfoIsFilledOutProperly() {
    var result = false;
    if ( ($("#password").val() != "") && ($("#email").val()!="") ) {
      result = true;
    }
    return result;
  }

  function sendUserInfoByAjax() {
      console.log("userInfo being sent");
      var firstName = $("#name").val();
      var email = $("#email").val();
      var password = $("#password").val();
      var userInfo = {
        "firstName":firstName,
        "email":email,
        "password": password
      };
      //return;
     $.ajax({
        url: '/sendUserInfo',
        type: 'POST',
        data: JSON.stringify(userInfo, null, '\t'),
        contentType: 'application/json;charset=UTF-8',
        success: function(response) {
          window.location = '/inbox'
        },
        error: function(error) {
          console.log(error);
        }
      });
    }

  $(document).on("click", ".login__submit", function(e) {
    console.log("submit is clicked");
    if (animating) return;
    animating = true;
    var that = this;
    ripple($(that), e);
    if ( userInfoIsFilledOutProperly() == true) {
      console.log("loaded properly");
      $(that).addClass("processing");
      sendUserInfoByAjax();
      // moves to successful login screen
      setTimeout(function() {
        $(that).addClass("success");
        setTimeout(function() {
          $app.show();
          $app.css("top");
          $app.addClass("active");
        }, submitPhase2 - 70);
        setTimeout(function() {
          $login.hide();
          $login.addClass("inactive");
          animating = false;
          $(that).removeClass("success processing");
        }, submitPhase2);
      }, submitPhase1);
    } else {
      $('.app__logout').html("<p>First name or email is invalid, please try again!");
    }
  });

  $(document).on("click", ".app__logout", function(e) {
    if (animating) return;
    $(".ripple").remove();
    animating = true;
    var that = this;
    $(that).addClass("clicked");
    setTimeout(function() {
      $app.removeClass("active");
      $login.show();
      $login.css("top");
      $login.removeClass("inactive");
    }, logoutPhase1 - 120);
    setTimeout(function() {
      $app.hide();
      animating = false;
      $(that).removeClass("clicked");
    }, logoutPhase1);
  });

  $(document).on("click", "#googleLogin", function(e) {
    window.location = '/login/google'
  });
});
