(function () {

  'use strict';

  angular.module('DashboardApp', [])

  .controller('DashboardController', ['$scope', '$log',
    function($scope, $log) {
    $scope.getResults = function() {
      $log.log("test");
    };
  }

  ]);

}());
