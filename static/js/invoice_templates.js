// Invoice Templates JavaScript

document.addEventListener('DOMContentLoaded', () => {
    const templateForm = document.getElementById('templateForm');
    if (templateForm) {
        templateForm.addEventListener('submit', handleTemplateSubmit);
    }
});

function showCreateModal() {
    document.getElementById('modalTitle').textContent = 'Create Template';
    document.getElementById('templateId').value = '';
    document.getElementById('templateName').value = '';
    document.getElementById('templateDescription').value = '';
    document.getElementById('templateHtml').value = '';
    document.getElementById('templateCss').value = '';
    document.getElementById('templateModal').classList.remove('hidden');
}

async function editTemplate(templateId) {
    try {
        const response = await fetch(`/invoice-templates/${templateId}`);
        
        if (response.status === 401 || response.status === 403) {
            window.location.href = '/login';
            return;
        }
        
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('modalTitle').textContent = 'Edit Template';
            document.getElementById('templateId').value = templateId;
            document.getElementById('templateName').value = data.template.name;
            document.getElementById('templateDescription').value = data.template.description || '';
            document.getElementById('templateHtml').value = data.template.html_template;
            document.getElementById('templateCss').value = data.template.css_styles || '';
            document.getElementById('templateModal').classList.remove('hidden');
        } else {
            alert('Error: ' + JSON.stringify(data));
        }
    } catch (error) {
        console.error('Failed to load template:', error);
        alert('Failed to load template');
    }
}

async function handleTemplateSubmit(event) {
    event.preventDefault();
    
    const templateId = document.getElementById('templateId').value;
    const name = document.getElementById('templateName').value;
    const description = document.getElementById('templateDescription').value;
    const htmlTemplate = document.getElementById('templateHtml').value;
    const cssStyles = document.getElementById('templateCss').value;
    
    const submitBtn = event.target.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving...';
    
    try {
        const url = templateId ? `/invoice-templates/${templateId}` : '/invoice-templates/create';
        const method = templateId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': '{{ csrf_token }}'
            },
            body: JSON.stringify({
                name: name,
                description: description,
                html_template: htmlTemplate,
                css_styles: cssStyles
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(data.message);
            closeModal();
            window.location.reload();
        } else {
            alert('Error: ' + data.message);
        }
    } catch (error) {
        console.error('Failed to save template:', error);
        alert('Failed to save template');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
}

async function deleteTemplate(templateId) {
    if (!confirm('Are you sure you want to delete this template?')) return;
    
    try {
        const response = await fetch(`/invoice-templates/${templateId}`, {
            method: 'DELETE',
            headers: {
                'X-CSRF-Token': '{{ csrf_token }}'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(data.message);
            window.location.reload();
        } else {
            alert('Error: ' + data.message);
        }
    } catch (error) {
        console.error('Failed to delete template:', error);
        alert('Failed to delete template');
    }
}

function closeModal() {
    document.getElementById('templateModal').classList.add('hidden');
}
