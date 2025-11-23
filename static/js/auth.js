// Avatar mapping
const avatarMap = {
    "default": "https://readdy.ai/api/search-image?query=professional%2520portrait%2520of%2520a%2520young%2520person%2520with%2520a%2520friendly%2520expression%252C%2520neutral%2520background%252C%2520high%2520quality%252C%2520professional%2520lighting%252C%2520detailed%2520facial%2520features%252C%2520modern%2520minimal%2520style&width=200&height=200&seq=1&orientation=squarish",
    "scholar": "https://readdy.ai/api/search-image?query=professional%2520portrait%2520of%2520a%2520young%2520woman%2520with%2520glasses%252C%2520neutral%2520background%252C%2520high%2520quality%252C%2520professional%2520lighting%252C%2520detailed%2520facial%2520features%252C%2520modern%2520minimal%2520style&width=200&height=200&seq=2&orientation=squarish",
    "executive": "https://readdy.ai/api/search-image?query=professional%2520portrait%2520of%2520a%2520middle-aged%2520man%2520in%2520business%2520attire%252C%2520neutral%2520background%252C%2520high%2520quality%252C%2520professional%2520lighting%252C%2520detailed%2520facial%2520features%252C%2520modern%2520minimal%2520style&width=200&height=200&seq=3&orientation=squarish",
    "creative": "https://readdy.ai/api/search-image?query=professional%2520portrait%2520of%2520a%2520young%2520person%2520with%2520creative%2520style%252C%2520neutral%2520background%252C%2520high%2520quality%252C%2520professional%2520lighting%252C%2520detailed%2520facial%2520features%252C%2520modern%2520minimal%2520style&width=200&height=200&seq=4&orientation=squarish",
    "professional": "https://readdy.ai/api/search-image?query=professional%2520portrait%2520of%2520a%2520woman%2520in%2520professional%2520attire%252C%2520neutral%2520background%252C%2520high%2520quality%252C%2520professional%2520lighting%252C%2520detailed%2520facial%2520features%252C%2520modern%2520minimal%2520style&width=200&height=200&seq=5&orientation=squarish"
};

// Function to update avatar in navbar
function updateNavbarAvatar(avatarType) {
    const avatarUrl = avatarMap[avatarType] || avatarMap["default"];
    const navbarAvatar = document.getElementById("navbarAvatar");
    const avatarImage = document.getElementById("avatarImage");
    if (navbarAvatar) navbarAvatar.src = avatarUrl;
    if (avatarImage) avatarImage.src = avatarUrl;
}

// Function to check authentication and update UI
async function checkAuth() {
    try {
        const response = await fetch("/api/check_auth");
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        const authButtons = document.getElementById("authButtons");
        const profileAvatar = document.getElementById("profileAvatar");
        
        if (data.authenticated) {
            if (authButtons) authButtons.classList.add("hidden");
            if (profileAvatar) {
                profileAvatar.classList.remove("hidden");
                updateNavbarAvatar(data.avatar);
            }
        } else {
            if (authButtons) authButtons.classList.remove("hidden");
            if (profileAvatar) profileAvatar.classList.add("hidden");
        }
    } catch (err) {
        console.error("Error checking auth:", err);
    }
}

// Function to handle logout
async function handleLogout() {
    try {
        const response = await fetch("/api/logout", {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        if (response.ok) {
            window.location.href = "/";
        }
    } catch (err) {
        console.error("Error logging out:", err);
    }
}

// Initialize auth check when page loads
document.addEventListener("DOMContentLoaded", checkAuth);

// Add logout button event listener if it exists
const logoutButton = document.getElementById("logoutButton");
if (logoutButton) {
    logoutButton.addEventListener("click", handleLogout);
} 