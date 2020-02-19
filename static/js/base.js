//Notification shower
if($('#notification').length > 0){
	$( "#notification" ).animate(
		{ left: "20px"},
		{ duration: 500}
	);
	setTimeout(function () {
		$( "#notification" ).animate(
			{ left: "-300px"},
			{ duration: 500}
		);
		setTimeout(function(){
			$('#notification').remove();
		}, 1000);
	}, 3000);
};

