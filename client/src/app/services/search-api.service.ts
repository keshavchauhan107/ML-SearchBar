import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

const API_BASE = 'http://127.0.0.1:8000';

export interface Suggestion {
  text: string;
  score: number;
}

export interface SuggestResponse {
  suggestions: Suggestion[];
}

export interface ImpressionEvent {
  type: 'impression';
  query: string;
  candidates: string[];
  clicked: string | null;
}

export interface ClickEvent {
  type: 'click';
  query: string;
  candidate: string;
}

@Injectable({
  providedIn: 'root',
})
export class SearchApiService {
  constructor(private http: HttpClient) {}

  getSuggestions(prefix: string, k = 10): Observable<SuggestResponse> {
    const params = new HttpParams()
      .set('prefix', prefix)
      .set('k', k.toString());

    return this.http.get<SuggestResponse>(`${API_BASE}/suggest`, { params });
  }

  logImpression(ev: ImpressionEvent): Observable<any> {
    return this.http.post(`${API_BASE}/log_event`, ev);
  }

  logClick(ev: ClickEvent): Observable<any> {
    return this.http.post(`${API_BASE}/log_event`, ev);
  }
}
