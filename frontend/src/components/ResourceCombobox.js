import React, { useState } from 'react';
import { Check, ChevronsUpDown } from 'lucide-react';
import { cn } from '../lib/utils';
import { Button } from './ui/button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from './ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from './ui/popover';

/**
 * Searchable resource picker (combobox) for allocations
 * Shows only active resources, filterable by name/role
 */
export function ResourceCombobox({ 
  value, 
  onChange, 
  resources = [], 
  disabled = false,
  placeholder = "Select resource...",
  testId = "resource-combobox"
}) {
  const [open, setOpen] = useState(false);
  
  // Filter only active resources
  const activeResources = resources.filter(r => r.active !== false);
  
  // Find selected resource
  const selectedResource = activeResources.find(r => r.id === value);
  
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between"
          disabled={disabled}
          data-testid={testId}
        >
          {selectedResource ? (
            <span className="flex items-center gap-2">
              <span className="font-medium">{selectedResource.name}</span>
              <span className="text-[#667085]">— {selectedResource.role}</span>
            </span>
          ) : (
            <span className="text-[#98A2B3]">{placeholder}</span>
          )}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[400px] p-0" style={{ zIndex: 9999 }}>
        <Command>
          <CommandInput placeholder="Search resources..." />
          <CommandList>
            <CommandEmpty>No resource found.</CommandEmpty>
            <CommandGroup>
              {activeResources.map((resource) => {
                const capacityInfo = resource.standard_capacity ? ` (${resource.standard_capacity}% capacity)` : '';
                return (
                  <CommandItem
                    key={resource.id}
                    value={`${resource.name} ${resource.role}`}
                    onSelect={() => {
                      onChange(resource.id);
                      setOpen(false);
                    }}
                    data-testid={`alloc-resource-option-${resource.id}`}
                  >
                    <Check
                      className={cn(
                        "mr-2 h-4 w-4",
                        value === resource.id ? "opacity-100" : "opacity-0"
                      )}
                    />
                    <div className="flex flex-col">
                      <span className="font-medium">{resource.name}</span>
                      <span className="text-xs text-[#667085]">
                        {resource.role}{capacityInfo}
                      </span>
                    </div>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
