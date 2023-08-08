// Import the functions you need from the SDKs you need
import {getAnalytics} from 'https://www.gstatic.com/firebasejs/10.1.0/firebase-analytics.js';
import {initializeApp} from 'https://www.gstatic.com/firebasejs/10.1.0/firebase-app.js';
// TODO: Add SDKs for Firebase products that you want to use
// https://firebase.google.com/docs/web/setup#available-libraries

// Your web app's Firebase configuration
// For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
  authDomain: 'lilac-386213.firebaseapp.com',
  projectId: 'lilac-386213',
  storageBucket: 'lilac-386213.appspot.com',
  messagingSenderId: '279475920249',
  appId: '1:279475920249:web:4680f6f21f8baf900c63a8',
  measurementId: 'G-LX8JBKFTT3'
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);
