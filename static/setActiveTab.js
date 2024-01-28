function setActiveTab(activeTab) {
    const tabs = ["mainTab", "settingsTab", "markovTab"]; // Add all tab IDs here
    const contents = ["mainContent", "settingsContent", "markovContent"]; // Add all content IDs here

    tabs.forEach((tab) => {
        document.getElementById(tab).classList.remove("active");
    });
    contents.forEach((content) => {
        document.getElementById(content).style.display = "none";
    });

    activeTab.classList.add("active");
    document.getElementById(
        activeTab.id.replace("Tab", "Content")
    ).style.display = "block";
}
function changeTheme() {
    var theme = document.getElementById("themeSelect").value;
    var link = "https://bootswatch.com/5/" + theme + "/bootstrap.min.css";
    if (theme === "default") {
        // Default Bootstrap theme
        link = "https://bootswatch.com/5/css/bootstrap.min.css";
    }
    document.getElementById("bootstrapCSS").href = link;
}
