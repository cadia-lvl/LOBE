const errorModal = $('#errorModal');
const errorTitleElement = document.querySelector('#errorTitleElement');
const errorMsgElement = document.querySelector('#errorMsgElement');
const errorStackElement = document.querySelector('#errorStackElement');

function promptError(errTitle, err, stack=""){
    errorTitleElement.innerHTML = errTitle;
    errorMsgElement.innerHTML = err;
    errorStackElement.innerHTML = stack;
    errorModal.modal('show');
}