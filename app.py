from flask import Flask, render_template, request, jsonify, send_file, session
from jobspy import scrape_jobs
import pandas as pd
import io
import uuid
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Store results temporarily (in production, consider using Redis or database)
results_cache = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search_jobs():
    try:
        # Get basic form data
        site_name = request.form.get('site_name')
        search_term = request.form.get('search_term')
        
        # Validate required fields
        if not site_name or not search_term:
            return jsonify({'error': 'Site name and search term are required'}), 400
        
        # Get all form parameters
        google_search_term = request.form.get('google_search_term', '').strip()
        location = request.form.get('location', '').strip()
        distance = request.form.get('distance')
        job_type = request.form.get('job_type', '').strip()
        results_wanted = int(request.form.get('results_wanted', 50))
        hours_old = request.form.get('hours_old')
        
        # Boolean parameters
        is_remote = request.form.get('is_remote') == 'on'
        easy_apply = request.form.get('easy_apply') == 'on'
        linkedin_fetch_description = request.form.get('linkedin_fetch_description') == 'on'
        enforce_annual_salary = request.form.get('enforce_annual_salary') == 'on'
        
        # Advanced parameters
        description_format = request.form.get('description_format', 'markdown')
        verbose = int(request.form.get('verbose', 2))
        user_agent = request.form.get('user_agent', '').strip()

        # LinkedIn company IDs
        linkedin_company_ids_str = request.form.get('linkedin_company_ids', '').strip()
        linkedin_company_ids = None
        if linkedin_company_ids_str:
            try:
                linkedin_company_ids = [int(x.strip()) for x in linkedin_company_ids_str.split(',') if x.strip()]
            except ValueError:
                return jsonify({'error': 'LinkedIn Company IDs must be comma-separated numbers'}), 400
        
        # Proxies
        proxies_str = request.form.get('proxies', '').strip()
        proxies = None
        if proxies_str:
            proxies = [line.strip() for line in proxies_str.split('\n') if line.strip()]
        
        # Convert empty strings to None for optional parameters
        distance = int(distance) if distance and distance.strip() else None
        hours_old = int(hours_old) if hours_old and hours_old.strip() else None
        location = location if location else None
        google_search_term = google_search_term if google_search_term else None
        job_type = job_type if job_type else None
        user_agent = user_agent if user_agent else None

        # Indeed / Glassdoor: sadece ana Location kullanılır; ülke location'dan çıkarılır
        country_indeed = None
        if site_name in ('indeed', 'glassdoor'):
            # Location'dan ülke tahmin et (JobSpy için country_indeed gerekli)
            _location_lower = (location or '').strip().lower()
            _country_from_location = (
                ('turkey', 'türkiye', 'istanbul', 'ankara', 'izmir'),
                ('netherlands', 'holland', 'amsterdam', 'rotterdam'),
                ('germany', 'deutschland', 'berlin', 'munich', 'frankfurt'),
                ('united kingdom', 'uk', 'london', 'manchester'),
                ('france', 'paris', 'lyon', 'marseille'),
                ('canada', 'toronto', 'vancouver', 'montreal'),
                ('australia', 'sydney', 'melbourne'),
                ('india', 'mumbai', 'bangalore', 'delhi'),
                ('spain', 'madrid', 'barcelona'),
                ('italy', 'rome', 'milan'),
                ('brazil', 'são paulo', 'rio', 'brasil'),
                ('mexico', 'méxico', 'mexico city'),
            )
            for names in _country_from_location:
                if any(n in _location_lower for n in names):
                    country_indeed = names[0]
                    break
            if not country_indeed:
                country_indeed = 'usa'
            # Location boşsa ülkeye göre varsayılan konum kullan (Indeed bazen boş location'da sonuç dönmüyor)
            if not location:
                _default_locations = {
                    'usa': 'United States', 'turkey': 'Turkey', 'uk': 'United Kingdom',
                    'germany': 'Germany', 'netherlands': 'Netherlands', 'france': 'France',
                    'canada': 'Canada', 'australia': 'Australia', 'india': 'India',
                    'spain': 'Spain', 'italy': 'Italy', 'brazil': 'Brazil', 'mexico': 'Mexico',
                }
                location = _default_locations.get(country_indeed) or 'United States'

            # Indeed limitations: only ONE of (hours_old), (job_type & is_remote), (easy_apply)
            selected_filter = None

            if hours_old is not None:
                selected_filter = 'hours_old'

            if job_type or is_remote:
                if selected_filter:
                    # Drop job_type/is_remote if another filter already selected
                    job_type = None
                    is_remote = False
                else:
                    selected_filter = 'job_type_is_remote'

            if easy_apply:
                if selected_filter:
                    # Drop easy_apply if another filter already selected
                    easy_apply = False
                else:
                    selected_filter = 'easy_apply'

        # LinkedIn limitations: only one of hours_old or easy_apply
        if site_name == 'linkedin' and hours_old is not None and easy_apply:
            # Prefer hours_old by default
            easy_apply = False
        
        print(f"Searching for: {search_term} on {site_name}")
        
        # Build parameters dictionary
        search_params = {
            'site_name': [site_name],
            'search_term': search_term,
            'location': location,
            'distance': distance,
            'is_remote': is_remote,
            'job_type': job_type,
            'easy_apply': easy_apply,
            'results_wanted': results_wanted,
            'description_format': description_format,
            'linkedin_fetch_description': linkedin_fetch_description,
            'linkedin_company_ids': linkedin_company_ids,
            'hours_old': hours_old,
            'enforce_annual_salary': enforce_annual_salary,
            'verbose': verbose,
            'user_agent': user_agent,
            'proxies': proxies,
            'country_indeed': country_indeed,
        }
        
        # Add Google search term if provided
        if google_search_term:
            search_params['google_search_term'] = google_search_term
        
        # Remove None values to use defaults
        search_params = {k: v for k, v in search_params.items() if v is not None}
        
        # Perform job search
        jobs = scrape_jobs(**search_params)
        
        # Generate unique ID for this search result
        result_id = str(uuid.uuid4())
        
        # Store results in cache with all search parameters
        cache_params = {
            'site_name': site_name,
            'search_term': search_term,
            'location': location,
            'distance': distance,
            'job_type': job_type,
            'results_wanted': results_wanted,
            'hours_old': hours_old,
            'is_remote': is_remote,
            'easy_apply': easy_apply,
            'linkedin_fetch_description': linkedin_fetch_description,
            'enforce_annual_salary': enforce_annual_salary,
            'description_format': description_format,
            'verbose': verbose,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Add optional parameters if they were provided
        if google_search_term:
            cache_params['google_search_term'] = google_search_term
        if linkedin_company_ids:
            cache_params['linkedin_company_ids'] = linkedin_company_ids
        if user_agent:
            cache_params['user_agent'] = user_agent
        if proxies:
            cache_params['proxies'] = proxies
        if country_indeed:
            cache_params['country_indeed'] = country_indeed
        
        results_cache[result_id] = {
            'jobs': jobs,
            'search_params': cache_params
        }
        
        # Convert DataFrame to HTML table
        if len(jobs) > 0:
            # Select key columns for display
            display_columns = ['title', 'company', 'location', 'job_type', 'date_posted', 'job_url', 'site']
            available_columns = [col for col in display_columns if col in jobs.columns]
            jobs_display = jobs[available_columns].copy()  # Use .copy() to avoid SettingWithCopyWarning
            
            # Make job URLs clickable
            if 'job_url' in jobs_display.columns:
                jobs_display.loc[:, 'job_url'] = jobs_display['job_url'].apply(
                    lambda x: f'<a href="{x}" target="_blank">View Job</a>' if pd.notna(x) else ''
                )
            
            table_html = jobs_display.to_html(
                classes='table table-striped table-hover',
                table_id='jobsTable',
                escape=False,
                index=False
            )
        else:
            table_html = '<p class="text-muted">No jobs found for your search criteria.</p>'
        
        return jsonify({
            'success': True,
            'table_html': table_html,
            'job_count': len(jobs),
            'result_id': result_id
        })
        
    except Exception as e:
        print(f"Error during job search: {str(e)}")
        return jsonify({'error': f'Search failed: {str(e)}'}), 500

@app.route('/download/<result_id>/<format>')
def download_results(result_id, format):
    try:
        if result_id not in results_cache:
            return "Results not found or expired", 404
        
        jobs = results_cache[result_id]['jobs']
        search_params = results_cache[result_id]['search_params']
        
        # Create filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"jobs_{search_params['search_term'].replace(' ', '_')}_{timestamp}"
        
        if format == 'csv':
            # Create CSV
            output = io.StringIO()
            jobs.to_csv(output, index=False)
            output.seek(0)
            
            # Convert to bytes
            csv_data = io.BytesIO()
            csv_data.write(output.getvalue().encode('utf-8'))
            csv_data.seek(0)
            
            return send_file(
                csv_data,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'{filename}.csv'
            )
            
        elif format == 'excel':
            # Create Excel file
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                jobs.to_excel(writer, sheet_name='Jobs', index=False)
                
                # Add search parameters as a separate sheet
                params_df = pd.DataFrame([search_params])
                params_df.to_excel(writer, sheet_name='Search_Parameters', index=False)
            
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'{filename}.xlsx'
            )
        
        else:
            return "Invalid format", 400
            
    except Exception as e:
        print(f"Error during download: {str(e)}")
        return f"Download failed: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
