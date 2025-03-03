// RENAMED to avoid conflict with settings.js
function changeTabTheme() {
    console.log("DEPRECATED: changeTabTheme in setActiveTab.js should not be used!");
    
    // Call the real changeTheme function from settings.js if it exists
    if (typeof window.changeTheme === 'function') {
        window.changeTheme();
    } else {
        console.error("Unable to find proper changeTheme function!");
    }
}
