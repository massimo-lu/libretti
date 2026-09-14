document.addEventListener('DOMContentLoaded', () => {
const tooltip = document.getElementById('tooltip');
const triggers = document.querySelectorAll('.note-trigger');
let activeTrigger = null;

// Function to position and show the tooltip
const showTooltip = (trigger) => {
    // If there's an active trigger, remove its active state
    if (activeTrigger && activeTrigger !== trigger) {
        activeTrigger.classList.remove('active');
    }

    activeTrigger = trigger;
    trigger.classList.add('active');
    
    const noteText = trigger.getAttribute('data-note');
    tooltip.textContent = noteText;
    
    // Make visible to calculate dimensions
    tooltip.classList.add('show');
    
    const triggerRect = trigger.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();
    
    const scrollY = window.scrollY || window.pageYOffset;
    const scrollX = window.scrollX || window.pageXOffset;

    // Default positioning: above the text
    let top = triggerRect.top + scrollY - tooltipRect.height - 12;
    let left = triggerRect.left + scrollX + (triggerRect.width / 2) - (tooltipRect.width / 2);

    // Reset arrow classes
    tooltip.classList.remove('arrow-top');

    // Check if tooltip goes above the top of the viewport
    if (triggerRect.top - tooltipRect.height - 12 < 0) {
        // Position below the text instead
        top = triggerRect.bottom + scrollY + 12;
        tooltip.classList.add('arrow-top');
    }

    // Check horizontal bounds
    const viewportWidth = window.innerWidth;
    if (left < 10) {
        left = 10; // Keep 10px margin from left edge
    } else if (left + tooltipRect.width > viewportWidth - 10) {
        left = viewportWidth - tooltipRect.width - 10; // Keep 10px margin from right edge
    }

    tooltip.style.top = `${top}px`;
    tooltip.style.left = `${left}px`;
};

const hideTooltip = () => {
    tooltip.classList.remove('show');
    if (activeTrigger) {
        activeTrigger.classList.remove('active');
        activeTrigger = null;
    }
};

// Attach click listeners to all note triggers
triggers.forEach(trigger => {
    trigger.addEventListener('click', (e) => {
        e.stopPropagation(); // Prevent document click listener from immediately firing
        if (activeTrigger === trigger) {
            hideTooltip();
        } else {
            showTooltip(trigger);
        }
    });
});

// Close tooltip when clicking anywhere else on the page
document.addEventListener('click', (e) => {
    if (activeTrigger && e.target !== tooltip) {
        hideTooltip();
    }
});

// Hide tooltip on scroll for better UX
window.addEventListener('scroll', () => {
    if (activeTrigger) {
        hideTooltip();
    }
}, { passive: true });

// Recalculate on window resize
window.addEventListener('resize', () => {
     if (activeTrigger) {
        hideTooltip();
     }
});
});
