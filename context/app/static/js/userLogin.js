angular.module('loginApp', []).config(function($interpolateProvider){
  $interpolateProvider.startSymbol('[[').endSymbol(']]');
}).controller('LoginController', ['$http', function($http) {
  var login = this;
  login.doLogin = function() {
    if(!login.email || !login.password) {
      login.error = "Email and password are required."
      return;
    }
    login.error = null;
    login.processing = true;
    $http.post('/sendUserInfo',{
        firstName: login.firstname ? login.firstname : '',
        email: login.email,
        password: login.password
    }).then(function(response) {
        // this callback will be called asynchronously
        login.processing = false;
        if(response.data.success) {
          window.location = '/inbox';
        } else {
          login.error = response.data.error;
        }
      }, function(response) {
          login.processing = false;
          login.error = response.data.error;
      });
  }
}]);
