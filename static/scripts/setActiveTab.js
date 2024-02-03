function changeTheme() {
    var theme = document.getElementById("themeSelect").value;
    console.log("Changing theme to:", theme); // Debugging line

    fetch(`/set_theme/${theme}`)
        .then(response => {
            if (response.ok) {
                var link = `https://bootswatch.com/5/${theme}/bootstrap.min.css`;
                console.log("Updating theme URL to:", link); // Debugging line
                document.getElementById("bootstrapCSS").href = link;
            } else {
                console.error('Error in response:', response);
            }
        })
        .catch(error => console.error('Error:', error));
}
