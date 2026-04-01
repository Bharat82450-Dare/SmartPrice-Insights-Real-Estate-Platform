import json
import pickle
import numpy as np
import pandas as pd
import re
import os
from typing import List, Dict, Optional, Union

import threading

# Global variables with type hints
__data_columns: List[str] = None
__locations: List[str] = None
__model: object = None
__df: pd.DataFrame = None


# Add a thread lock for safe DataFrame updates
__data_lock = threading.Lock()

def add_property(property_data: Dict) -> None:
    """
    Add a new property to the dataset (in-memory and CSV)
    
    Args:
        property_data: Dictionary containing property details matching CSV columns
    """
    global __df
    
    if not isinstance(property_data, dict):
        raise ValueError("property_data must be a dictionary")
    
    required_fields = {
        'area_type', 'availability', 'location', 'size', 
        'total_sqft', 'bath', 'balcony', 'price'
    }
    
    # Validate input
    missing_fields = required_fields - set(property_data.keys())
    if missing_fields:
        raise ValueError(f"Missing required fields: {missing_fields}")
    
    try:
        # Clean the new property data
        cleaned_data = {
            'area_type': str(property_data.get('area_type', '')).strip(),
            'availability': str(property_data.get('availability', 'Ready To Move')).strip(),
            'location': str(property_data.get('location', '')).strip().lower(),
            'size': str(property_data.get('size', '')),
            'society': str(property_data.get('society', '')).strip(),
            'total_sqft': __clean_sqft(property_data.get('total_sqft', 0)),
            'bath': int(property_data.get('bath', 1)),
            'balcony': int(property_data.get('balcony', 0)),
            'price': float(property_data.get('price', 0)),
            'username': str(property_data.get('username', 'anonymous')),
            'timestamp': str(property_data.get('timestamp', '')),
            'title': str(property_data.get('title', '')),
            'description': str(property_data.get('description', '')),
            'contact': str(property_data.get('contact', '')),
            'image_path': str(property_data.get('image_path', ''))
        }
        
        # Add 'bhk' for in-memory DataFrame
        in_memory_data = cleaned_data.copy()
        in_memory_data['bhk'] = __extract_bhk(cleaned_data['size'])
        
        # Thread-safe DataFrame update
        with __data_lock:
            # Add to in-memory DataFrame
            new_row = pd.DataFrame([in_memory_data])
            global __df
            __df = pd.concat([__df, new_row], ignore_index=True)
            
            # Append to CSV (persistent storage)
            # Ensure columns match CSV order
            csv_cols = ['area_type', 'availability', 'location', 'size', 'society', 'total_sqft', 'bath', 'balcony', 'price', 'username', 'timestamp', 'title', 'description', 'contact', 'image_path']
            pd.DataFrame([cleaned_data])[csv_cols].to_csv(
                "server/bengaluru_house_prices.csv",
                mode='a',
                header=False,
                index=False
            )
            
            # Update locations cache
            global __locations
            loc = cleaned_data['location'].title()
            if loc not in __locations:
                __locations = sorted(__df['location'].str.title().unique())
                
    except Exception as e:
        raise ValueError(f"Failed to add property: {str(e)}")

def load_saved_artifacts() -> None:
    """Load all required artifacts for the application"""
    global __data_columns, __locations, __model, __df
    
    print("Loading saved artifacts...")
    
    try:
        # 1. Load columns data
        columns_path = "server/artifacts/columns.json"
        if not os.path.exists(columns_path):
            raise FileNotFoundError(f"Columns file not found at {columns_path}")
            
        with open(columns_path, "r") as f:
            __data_columns = json.load(f)['data_columns']
            __locations = __data_columns[3:]  # first 3 are sqft, bath, bhk
        
        # 2. Load ML model
        model_path = "server/artifacts/bangalore_home_prices_model3.pickle"
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at {model_path}")
            
        with open(model_path, "rb") as f:
            __model = pickle.load(f)
        
        # 3. Load and clean dataset
        data_path = "server/bengaluru_house_prices.csv"
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"Data file not found at {data_path}")
            
        __df = pd.read_csv(data_path)
        print(f"Initial dataset shape: {__df.shape}")
        
        # Data cleaning pipeline
        __clean_data()
        
        print(f"Final dataset shape: {__df.shape}")
        print("Artifacts loaded successfully")
        
    except Exception as e:
        print(f"Error loading artifacts: {str(e)}")
        raise

def __clean_data() -> None:
    """Clean and preprocess the housing data"""
    global __df
    
    # 1. Extract BHK from size
    __df['bhk'] = __df['size'].apply(__extract_bhk)
    
    # 2. Clean square footage
    __df['total_sqft'] = __df['total_sqft'].apply(__clean_sqft)
    
    # 3. Drop rows with missing essential values
    initial_count = len(__df)
    __df.dropna(subset=['bhk', 'total_sqft', 'bath', 'price', 'location'], inplace=True)
    print(f"Removed {initial_count - len(__df)} rows with missing values")
    
    # 4. Filter unreasonable values
    __df = __df[__df['total_sqft'] > 300]  # minimum reasonable size
    __df = __df[__df['price'] > 0]  # positive prices only
    __df = __df[__df['bhk'] > 0]  # at least 1 BHK
    
    # 5. Clean text columns
    __df['location'] = __df['location'].str.strip().str.lower()
    __df['society'] = __df['society'].str.strip()
    __df['area_type'] = __df['area_type'].str.strip()

def __extract_bhk(size_str: str) -> Optional[int]:
    """Extract BHK number from size string"""
    try:
        return int(re.search(r'\d+', str(size_str)).group())
    except (AttributeError, TypeError, ValueError):
        return None

def __clean_sqft(sqft_str: Union[str, float]) -> Optional[float]:
    """Convert various sqft formats to numeric value"""
    try:
        val = str(sqft_str).lower()
        val = val.replace('sq.ft', '').replace('sqft', '').replace(',', '').strip()
        match = re.match(r'^(\d+\.?\d*)\s*-?\s*(\d+\.?\d*)?$', val)
        
        if match:
            if match.group(2):  # Range value (e.g., 1000-1500)
                return (float(match.group(1)) + float(match.group(2))) / 2
            return float(match.group(1))
        return None
    except:
        return None

def get_estimated_price(location: str, sqft: float, bhk: int, bath: int) -> float:
    """Get price estimate using ML model"""
    try:
        loc_index = __data_columns.index(location.lower())
    except ValueError:
        loc_index = -1  # location not found

    x = np.zeros(len(__data_columns))
    x[0] = sqft
    x[1] = bath
    x[2] = bhk
    if loc_index >= 0:
        x[loc_index] = 1

    return round(__model.predict([x])[0], 2)

def apply_price_adjustments(base_price: float, options: Dict) -> float:
    """Apply price adjustments based on additional features"""
    adjusted_price = base_price
    
    # Society premium (0-15%)
    if options.get('society'):
        adjusted_price *= 1.05  # 5% premium for known societies
    
    # Area type adjustments
    area_type = options.get('area_type', '').lower()
    if area_type == 'plot area':
        adjusted_price *= 0.95
    elif area_type == 'carpet area':
        adjusted_price *= 1.1
    
    # Amenities (2% per premium amenity)
    amenities = options.get('amenities', [])
    premium_amenities = {'pool', 'gym', 'security', 'lift'}
    premium_count = len(set(amenities) & premium_amenities)
    adjusted_price *= 1 + (0.03 * premium_count)
    
    # Floor adjustment (1% per floor above ground)
    floor = max(0, options.get('floor', 0))
    if floor > 0:
        adjusted_price *= 1 + (0.01 * min(floor, 10))  # Max 10% increase
    
    # Age depreciation (1% per year after first 5 years)
    age = max(0, options.get('age', 0))
    if age > 5:
        adjusted_price *= 1 - (0.01 * min(age-5, 30))  # Max 30% depreciation
    
    return round(adjusted_price, 2)

def get_location_names() -> List[str]:
    """Get unique sorted location names"""
    if __df is None:
        raise ValueError("Data not loaded - call load_saved_artifacts() first")
    return sorted(__df['location'].str.title().unique())

def get_area_types() -> List[str]:
    """Get unique sorted area types"""
    if __df is None:
        raise ValueError("Data not loaded - call load_saved_artifacts() first")
    return sorted(__df['area_type'].unique())

def get_society_names(location_filter: Optional[str] = None) -> List[Dict]:
    """Get society data with optional location filter"""
    if __df is None:
        raise ValueError("Data not loaded - call load_saved_artifacts() first")
    
    try:
        df_filtered = __df.copy()
        
        # Apply location filter if provided
        if location_filter:
            location_filter = str(location_filter).strip().lower()
            df_filtered = df_filtered[
                df_filtered['location'].str.strip().str.lower() == location_filter
            ]
            if df_filtered.empty:
                return []
        
        # Group and aggregate society data
        societies = []
        grouped = df_filtered.groupby(['society', 'location', 'area_type'])
        
        for (society, location, area_type), group in grouped:
            # Skip if essential data is missing
            if pd.isna(society) or pd.isna(location) or pd.isna(area_type):
                continue
                
            try:
                # Convert and clean numerical columns
                sqft = pd.to_numeric(group['total_sqft'], errors='coerce').dropna()
                bhk = pd.to_numeric(group['bhk'], errors='coerce').dropna().astype(int)
                bath = pd.to_numeric(group['bath'], errors='coerce').dropna().astype(int)
                price = pd.to_numeric(group['price'], errors='coerce').dropna()
                
                if len(sqft) == 0 or len(price) == 0:
                    continue
                    
                societies.append({
                    "name": str(society) if pd.notna(society) else "Unnamed Society",
                    "location": str(location).title(),
                    "area_type": str(area_type),
                    "bhk_available": sorted(bhk.unique().tolist()),
                    "bath_available": sorted(bath.unique().tolist()),
                    "min_area": int(sqft.min()),
                    "max_area": int(sqft.max()),
                    "min_price": int(price.min()),
                    "max_price": int(price.max()),
                    "base_price": round(price.mean(), 2),
                    "amenities": ["Park", "Gym", "Pool", "Security", "Lift"],  # Mock - replace with real data
                    "lat": 12.9716,  # Mock coordinates
                    "lng": 77.5946   # Should be replaced with actual data
                })
            except Exception as e:
                print(f"Error processing society {society}: {str(e)}")
                continue
                
        return sorted(societies, key=lambda x: x['name'])
    except Exception as e:
        print(f"Error in get_society_names: {str(e)}")
        raise