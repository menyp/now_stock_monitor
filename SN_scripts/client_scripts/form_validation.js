/**
 * Client-side Form Validation for ServiceNow
 * 
 * Purpose: Validates form fields before submission
 * Type: Client Script (onSubmit)
 * Table: incident
 */
function onSubmit() {
    // Get form fields
    var shortDescription = g_form.getValue('short_description');
    var category = g_form.getValue('category');
    var priority = g_form.getValue('priority');
    
    // Validate short description
    if (shortDescription.length < 10) {
        alert('Short description must be at least 10 characters long.');
        return false;
    }
    
    // Validate category selection
    if (category === '') {
        alert('You must select a category.');
        return false;
    }
    
    // Validate priority based on category
    if (category === 'network' && priority > 2) {
        if (!confirm('Network issues typically require higher priority. Continue with current priority?')) {
            return false;
        }
    }
    
    return true;
}
