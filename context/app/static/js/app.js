angular.module('nousApp', []).config(function($interpolateProvider){
  $interpolateProvider.startSymbol('[[').endSymbol(']]');
}).factory('StatusChecker', function($http,$q){
 return {
      poll : function(api){
          var deferred = $q.defer();
          $http.get(api).then(function (response) {
            deferred.resolve(response.data);
          });
          return deferred.promise;
      }

  }
}).controller('AppController', ['$http', 'StatusChecker', function($http, StatusChecker) {
  var app = this;
  app.test = 'This is just a test';
  var timer = null;
  app.getContacts = function() {
    $http.get('/get-contacts').
      then(function(response) {
        // this callback will be called asynchronously
        console.log(response)
        app.contacts = response.data;
      }, function(response) {
        // called asynchronously if an error occurs
        // or server returns response with an error status.
      });
  }

  var checkStatus = function () {
    StatusChecker.poll('/check-status').then(function(data){
        if(data.pending_contacts &&
          (!app.contacts || app.contacts.contacts.length == 0)) {
          app.getContacts();
        }
        if(app.status.pending_analysis == true
          && data.pending_analysis == false) {
            app.loadInbox();
          }
        app.status = data;
    });
  };

  app.contactText = function(contact) {
    return contact.name ? contact.name : contact.email;
  }
  app.contactExists = function(contact) {
    for(i=0;i<app.contacts.selectedContacts.length;i++) {
      var selected = app.contacts.selectedContacts[i];
      if(selected && selected.emails) {
        for(x=0;x<selected.emails.length;x++) {
          if(selected.emails[x] === contact.email) return true;
        }
      }
    }
    return false;
  }

  app.contactImg = function(message) {
    return message.person_info[message.addresses.from.email].thumbnail;
  }

  app.contactName = function(message) {
    return message.addresses.from.name ? message.addresses.from.name : message.address.from.email;
  }

  app.toggleContact = function(contact) {
    var contactEmailObj = {
      "email":contact.email
    };
    $http.post('/selectContact', contactEmailObj).
      then(function(response) {
        // this callback will be called asynchronously
        console.log(response)
        app.contacts.selectedContacts.push(response.data);
        contact.added = true;
      }, function(response) {
        // called asynchronously if an error occurs
        // or server returns response with an error status.
      });
  }

  app.doAnalysis = function() {
    $http.post('/do-analysis', {}).
      then(function(response) {
        // this callback will be called asynchronously
        console.log(response)
        app.contacts.selectedContacts.push(response.data);
        app.status.pending_analysis = true;
        app.status.pending_contacts = false;
      }, function(response) {
        // called asynchronously if an error occurs
        // or server returns response with an error status.
      });
  }

  app.loadInbox = function() {
    $http.get('/get-inbox').
      then(function(response) {
        // this callback will be called asynchronously
        console.log(response)
        app.inbox = response.data;
        app.showInbox = true;
        window.clearInterval(timer);
      }, function(response) {
        // called asynchronously if an error occurs
        // or server returns response with an error status.
      });
  }

  $http.get('/check-status').
    then(function(response) {
      // this callback will be called asynchronously
      console.log(response)
      app.status = response.data;
      if(app.status.pending_contacts) {
        app.getContacts();
      } else if(!app.status.pending_sync && !app.status.pending_analysis) {
        app.showInbox = true;
        app.loadInbox();
      }
      timer = setInterval(checkStatus, 10000);
    }, function(response) {
      // called asynchronously if an error occurs
      // or server returns response with an error status.
    });
}]);

var contacts = []
var timespan = 100;
$('#contactsModal').on('shown.bs.modal', function () {
  //refreshContactModal();
})

function refreshContactModal() {
  //$('#modalContacts').empty();
  for(i=0;i<contacts.contacts.length;i++) {
    var contact = contacts.contacts[i]
    var text = contact.name ? contact.name : contact.email;
    var contactAdded = contactExists(contact.email);
    var button = '';
    if(contactAdded) {
      button = '<a class="btn btn-xs btn-default pull-right" href="javascript: removeContact(' + i + ')">Remove</a>';
    } else {
      button = '<a class="btn btn-xs btn-default pull-right" href="javascript: addContact(' + i + ')">Add</a>';
    }
    $('#modalContacts').append('<tr><td class="col-sm-10">'+ text + '</td><td>' + button + '</td></tr>');
  }
}

function contactExists(email) {
  for(i=0;i<contacts.selectedContacts.length;i++) {
    var contact = contacts.selectedContacts[i];
    for(x=0;x<contact.emails.length;x++) {
      if(contact.emails[x] === email) return true;
    }
  }
  return false;
}

function getBig5() {
  /** Example call for personality
  *   get-fullBig5 gets the full personality insight JSON
  *   Takes email as { email: anEmailAddress }
  **/
  $.ajax({
    url: '/get-fullBig5',
    type: 'POST',
    data: JSON.stringify(data, null, '\t'),
    contentType: 'application/json;charset=UTF-8',
    success: function(response) {
    console.log(JSON.parse(response))
    },
    error: function(error) {
     console.log(error);
    }
  });
}

function getMessageTone() {
  /** Example call for messages and tone
  *   get-messages returns messages with nested tone JSON
  *   Takes email as { email: anEmailAddress }
  **/
  $.ajax({
    url: '/get-messages',
    type: 'POST',
    data: JSON.stringify(data, null, '\t'),
    contentType: 'application/json;charset=UTF-8',
    success: function(response) {
     console.log(JSON.parse(response))
    },
    error: function(error) {
      console.log(error);
    }
  });
}
