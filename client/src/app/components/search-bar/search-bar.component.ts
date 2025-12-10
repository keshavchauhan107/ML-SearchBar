import { Component, OnDestroy, OnInit } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import {
  debounceTime,
  distinctUntilChanged,
  filter,
  switchMap,
  tap,
  Subscription,
} from 'rxjs';
import {
  SearchApiService,
  Suggestion,
} from '../../services/search-api.service';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-search-bar',
  imports: [ReactiveFormsModule,CommonModule],
  templateUrl: './search-bar.component.html',
})
export class SearchBarComponent implements OnInit, OnDestroy {
  searchControl = new FormControl('');
  suggestions: Suggestion[] = [];
  isOpen = false;

  private sub?: Subscription;
  private lastQueryForImpression = '';   // to send correct query in impression
  private lastCandidates: string[] = []; // to re-use when logging click

  constructor(private api: SearchApiService) {}

  ngOnInit(): void {
    this.sub = this.searchControl.valueChanges
      .pipe(
        debounceTime(250),
        filter((val) => (val ?? '').trim().length > 0),
        distinctUntilChanged(),
        tap((val) => {
          this.isOpen = true;
        }),
        switchMap((val) => {
          const prefix = (val ?? '').trim();
          this.lastQueryForImpression = prefix;
          return this.api.getSuggestions(prefix);
        }),
        tap((res) => {
          // after suggestions are fetched → log impression
          this.suggestions = res.suggestions ?? [];
          this.lastCandidates = this.suggestions.map((s) => s.text);

          if (this.lastCandidates.length > 0) {
            this.api
              .logImpression({
                type: 'impression',
                query: this.lastQueryForImpression,
                candidates: this.lastCandidates,
                clicked: null,
              })
              .subscribe({
                error: (err) => console.error('Impression log failed', err),
              });
          }
        })
      )
      .subscribe();
  }

  onSuggestionClick(s: Suggestion): void {
    const query = this.lastQueryForImpression || (this.searchControl.value ?? '');
    this.searchControl.setValue(s.text, { emitEvent: false }); // don’t trigger new suggest
    this.isOpen = false;

    // log click
    this.api
      .logClick({
        type: 'click',
        query: query,
        candidate: s.text,
      })
      .subscribe({
        error: (err) => console.error('Click log failed', err),
      });

    // here, normal search action can continue (navigate, call search API, etc.)
  }

  onBlur(): void {
    // optional: small delay if using click on suggestion
    setTimeout(() => {
      this.isOpen = false;
    }, 150);
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }
}

