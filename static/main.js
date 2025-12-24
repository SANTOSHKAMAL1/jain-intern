// Geolocation helper
function getLocation(callback) {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            position => {
                callback(null, position.coords.latitude, position.coords.longitude);
            },
            error => {
                callback(error.message);
            }
        );
    } else {
        callback("Geolocation is not supported by this browser.");
    }
}

// Auto-dismiss alerts after 5 seconds
document.addEventListener('DOMContentLoaded', () => {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });
});