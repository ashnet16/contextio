angular.module('nousApp', []).config(function($interpolateProvider){
  $interpolateProvider.startSymbol('[[').endSymbol(']]');
}).controller('MenuController', [function() {
  var menu = this
  menu.route = window.location.pathname;
}]).factory('StatusChecker', function($http,$q){
 return {
      poll : function(api){
          var deferred = $q.defer();
          $http.get(api).then(function (response) {
            deferred.resolve(response.data);
          });
          return deferred.promise;
      }

  }
}).controller('InboxController', ['$http', 'StatusChecker', function($http, StatusChecker) {
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
        if(data.redirect) window.location = '/'
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
    return contact.name ? contact.name + ' (' + contact.email + ')' : contact.email;
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
    return message.addresses.from.name ? message.addresses.from.name : message.addresses.from.email;
  }

  app.toggleContact = function(contact, index) {
    var contactEmailObj = {
      "email":contact.email
    };
    if(app.contactExists(contact)) {
      $http.post('/removeContact', { contact: { name: contact.name, emails: contact.emails } }).
        then(function(response) {
          // this callback will be called asynchronously
          if(response.data)
            app.contacts.selectedContacts.splice(index, 1);
          // TODO display an error to the user
        }, function(response) {
          // called asynchronously if an error occurs
          // or server returns response with an error status.
        });
    } else {
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
}]).controller('PersonalityController', ['$http', function($http) {
  var dashboard = this;
  
  // initialize a merged data object containing both datasets - used in the grouped bar chart
  dashboard.mergedViewData = [
     dashboard.userPersonality,
     dashboard.contactPersonality
   ]

  dashboard.getContactPersonality = function(update) {

    // initialize the default value of update to false
    update = update || false


    $http.post('/get-fullBig5', { email: dashboard.selectedContact.emails[0]}).
      then(function(response) {
        // this callback will be called asynchronously
        dashboard.contactPersonality = response.data;
        
        // initialize array for contact data used in grouped bar chart
        contactData= []
        
        
      // get the values of the data needed for the contact user
      dashboard.contactPersonality.children.forEach(function(d) {
        obj = {}
        obj.cat = d.name
        obj.name = dashboard.selectedContact.name
        obj.value = d.percentage
        obj.data = []
        d.children.forEach(function(dd){
          obj.data.push(dd.percentage)
        })
        contactData.push(obj)
      })
  

      // the update value is assigned in the template
      if (update == true) {
        console.log(contactData)
          // updates the contact personality chart with the new contact's data
          // buildPersonalityChart(dashboard.contactPersonality, "contact-chart", update)
          buildPersonalityChart(contactData, update)
    } else {
          buildPersonalityChart(contactData)
        

      // buildPersonalityChart(dashboard.contactPersonality, "contact-chart")
    }

      }, function(response) {
        // called asynchronously if an error occurs
        // or server returns response with an error status.
      });
  }

  $http.post('/get-fullBig5', userEmail).
    then(function(response) {
      // this callback will be called asynchronously
      dashboard.userPersonality = response.data;
      
      // set the value of the user personality 
      dashboard.mergedViewData[0] = dashboard.userPersonality

      // build the user personality chart
      // buildPersonalityChart(dashboard.userPersonality, "user-chart")


    }, function(response) {

      // called asynchronously if an error occurs
      // or server returns response with an error status.
    });
    $http.get('/get-selected-contacts').
      then(function(response) {
        // this callback will be called asynchronously
        dashboard.contacts = response.data;
        dashboard.selectedContact = dashboard.contacts[0]
        dashboard.getContactPersonality();

      }, function(response) {
        // called asynchronously if an error occurs
        // or server returns response with an error status.
      });
}]).controller('ToneController', ['$http', function($http) {
  var dashboard = this;
  dashboard.toneSwitch = 'user';
  dashboard.rollupTone = function() {
    dashboard.toneRollup = {
      Agreeableness: 0,
      Conscientiousness: 0,
      Openness: 0,
      Tentative: 0,
      Analytical: 0,
      Confident: 0,
      Negative: 0,
      Anger: 0,
      Cheerfulness: 0,
    };
    for(i=0;i<dashboard.selectedTone.length;i++) {
      var item = dashboard.selectedTone[i].tone
      dashboard.toneRollup.Agreeableness += item['Social Tone.Agreeableness'];
      dashboard.toneRollup.Conscientiousness += item['Social Tone.Conscientiousness'];
      dashboard.toneRollup.Openness += item['Social Tone.Openness'];
      dashboard.toneRollup.Tentative += item['Writing Tone.Tentative'];
      dashboard.toneRollup.Analytical += item['Writing Tone.Analytical'];
      dashboard.toneRollup.Confident += item['Writing Tone.Confident'];
      dashboard.toneRollup.Negative += item['Emotion Tone.Negative'];
      dashboard.toneRollup.Anger += item['Emotion Tone.Anger'];
      dashboard.toneRollup.Cheerfulness += item['Emotion Tone.Cheerfulness'];
    }
  }
  dashboard.getContactTone = function(update) {

    // initialize the default value of update to false
    update = update || false


    var data = {}
    if(dashboard.toneSwitch==='contact') {
      if(!dashboard.selectedContact) return dashboard.selectedTone = null;
      data.to = dashboard.selectedContact.emails[0]
    }
    $http.post('/get-tone', data).
      then(function(response) {
        // this callback will be called asynchronously
        dashboard.selectedTone = response.data;
        dashboard.rollupTone();

    // the update value is assigned in the template
    if (update == true) {

          // update tone chart with new contact's data
          toneChart(dashboard.selectedTone, update)

    }

      }, function(response) {
        // called asynchronously if an error occurs
        // or server returns response with an error status.
      });
  }

  $http.post('/get-tone', {}).
    then(function(response) {
      // this callback will be called asynchronously
      dashboard.selectedTone = response.data;
      dashboard.rollupTone();
      toneChart(dashboard.selectedTone)

    }, function(response) {
      // called asynchronously if an error occurs
      // or server returns response with an error status.
    });
    $http.get('/get-selected-contacts').
      then(function(response) {
        // this callback will be called asynchronously
        dashboard.contacts = response.data;
      }, function(response) {
        // called asynchronously if an error occurs
        // or server returns response with an error status.
      });
}]).filter('percentage', ['$filter', function ($filter) {
  return function (input, decimals) {
    return $filter('number')(input * 100, decimals) + '%';
  };
}]).controller('ContactsController', ['$http', 'StatusChecker', function($http, StatusChecker) {
  var contactCtrl = this;
  contactCtrl.status = {}
  var timer = null;
  var checkStatus = function () {
    StatusChecker.poll('/check-status').then(function(data){
        if(contactCtrl.status.pending_analysis == true
          && data.pending_analysis == false) {
            window.clearInterval(timer);
          }
        contactCtrl.status = data;
    });
  };

  contactCtrl.doAnalysis = function() {
    $http.post('/do-analysis', {}).
      then(function(response) {
        // this callback will be called asynchronously
        console.log(response)
        contactCtrl.status.pending_analysis = true;
        timer = setInterval(checkStatus, 10000);
      }, function(response) {
        // called asynchronously if an error occurs
        // or server returns response with an error status.
      });
  }
  contactCtrl.contactText = function(contact) {
    return contact.name ? contact.name + ' (' + contact.email + ')' : contact.email;
  }
  contactCtrl.contactExists = function(contact) {
    for(i=0;i<contactCtrl.contacts.selectedContacts.length;i++) {
      var selected = contactCtrl.contacts.selectedContacts[i];
      if(selected && selected.emails) {
        for(x=0;x<selected.emails.length;x++) {
          if(selected.emails[x] === contact.email) return true;
        }
      }
    }
    return false;
  }

  contactCtrl.toggleContact = function(contact, index) {
    var contactEmailObj = {
      "email":contact.email
    };
    if(contactCtrl.contactExists(contact)) {
      $http.post('/removeContact', { contact: contact }).
        then(function(response) {
          // this callback will be called asynchronously
          if(response.data)
            contactCtrl.contacts.selectedContacts.splice(index, 1);
          // TODO display an error to the user
        }, function(response) {
          // called asynchronously if an error occurs
          // or server returns response with an error status.
        });
    } else {
      $http.post('/selectContact', contactEmailObj).
        then(function(response) {
          // this callback will be called asynchronously
          console.log(response)
          contactCtrl.contacts.selectedContacts.push(response.data);
          contactCtrl.added = true;
        }, function(response) {
          // called asynchronously if an error occurs
          // or server returns response with an error status.
        });
    }
  }

  $http.get('/get-contacts').
    then(function(response) {
      // this callback will be called asynchronously
      console.log(response)
      contactCtrl.contacts = response.data;
    }, function(response) {
      // called asynchronously if an error occurs
      // or server returns response with an error status.
    });
    $http.get('/check-status').
      then(function(response) {
        // this callback will be called asynchronously
        console.log(response)
        contactCtrl.status = response.data;
        if(contactCtrl.status.pending_analysis) {
          timer = setInterval(checkStatus, 10000);
        }
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
