import os
import json
import uuid
import warnings
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
import joblib
import numpy as np
import pandas as pd

from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour
from spade.message import Message

from Environment.environment import INTERSECTION_IDS


class DisruptionManagementAgent(Agent):
    """
    Disruption Management Agent that uses ML models to predict disruptions.
    
    Responsibilities:
    - Load ML models (classification or regression) based on .env configuration
    - Collect traffic metrics from environment
    - Predict disruption occurrences at intersections
    - Broadcast warnings to other agents via FIPA Inform Protocol
    - Update environment with predicted disruptions for visual display
    """
    
    def __init__(self, jid, password, environment):
        super().__init__(jid, password)
        self.environment = environment
        self.id = jid
        
        # Load .env file
        load_dotenv()
        self.model_type = os.getenv("MODEL", "classification").lower()
        
        # Validate model type
        if self.model_type not in ["classification", "regression"]:
            print(f"[DISRUPTION MANAGEMENT] Invalid MODEL value: {self.model_type}. Defaulting to 'classification'")
            self.model_type = "classification"
        
        # Load ML model
        self.model = None
        self.model_path = None
        self._load_model()
        
        # Traffic light agent JIDs for broadcasting
        self.traffic_light_jids = [
            "semaforos_1@localhost",
            "semaforos_2@localhost",
            "semaforos_3@localhost",
            "semaforos_4@localhost",
            "semaforos_5@localhost",
            "semaforos_6@localhost",
        ]
        
        # Prediction threshold for regression models
        self.regression_threshold = 0.5
        
        # Track last predictions for comparison
        self.last_predictions = {}
    
    def _load_model(self):
        """Load the ML model based on MODEL environment variable."""
        model_filename = f"modelo_{self.model_type}.pkl"
        self.model_path = Path("ml_models") / model_filename
        
        try:
            if not self.model_path.exists():
                raise FileNotFoundError(f"Model file not found: {self.model_path}")
            
            # Try loading with compatibility mode for numpy version mismatches
            try:
                # First attempt: standard load
                self.model = joblib.load(self.model_path)
            except (ValueError, TypeError, AttributeError) as e:
                error_str = str(e).lower()
                if "numpy.dtype size changed" in str(e) or "binary incompatibility" in error_str:
                    # Numpy version mismatch - try workaround
                    print(f"[DISRUPTION MANAGEMENT {self.jid}] WARNING: NumPy version mismatch detected.")
                    print(f"[DISRUPTION MANAGEMENT] Attempting compatibility workaround...")
                    try:
                        # Workaround: suppress numpy warnings and try loading
                        # This handles numpy version mismatches by ignoring dtype size warnings
                        old_err = np.seterr(all='ignore')
                        
                        with warnings.catch_warnings():
                            warnings.filterwarnings("ignore", category=RuntimeWarning)
                            warnings.filterwarnings("ignore", category=UserWarning)
                            # Suppress the specific numpy dtype warning
                            warnings.filterwarnings("ignore", message=".*numpy.dtype size changed.*")
                            # Try loading again
                            self.model = joblib.load(self.model_path)
                        
                        # Restore numpy error settings
                        np.seterr(**old_err)
                        
                        print(f"[DISRUPTION MANAGEMENT {self.jid}] Model loaded with compatibility workaround.")
                        print(f"[DISRUPTION MANAGEMENT] NOTE: Consider retraining model with current numpy version for best compatibility.")
                    except Exception as e2:
                        # Restore numpy error settings if we saved them
                        try:
                            np.seterr(**old_err)
                        except:
                            pass
                        
                        print(f"[DISRUPTION MANAGEMENT {self.jid}] ERROR: Failed to load model even with compatibility mode.")
                        print(f"[DISRUPTION MANAGEMENT] Error details: {e2}")
                        raise e2
                else:
                    raise e
            
            # print(f"[DISRUPTION MANAGEMENT {self.jid}] Loaded {self.model_type} model from {self.model_path}")
        except FileNotFoundError as e:
            print(f"[DISRUPTION MANAGEMENT {self.jid}] ERROR: {e}")
            print(f"[DISRUPTION MANAGEMENT] Model file path: {self.model_path}")
            print(f"[DISRUPTION MANAGEMENT] Please ensure the model file exists in the ml_models/ directory")
            self.model = None
        except Exception as e:
            error_msg = str(e)
            print(f"[DISRUPTION MANAGEMENT {self.jid}] ERROR loading model: {error_msg}")
            print(f"[DISRUPTION MANAGEMENT] Model file path: {self.model_path}")
            
            # Provide specific guidance for common errors
            if "numpy.dtype size changed" in error_msg or "binary incompatibility" in error_msg.lower():
                print(f"[DISRUPTION MANAGEMENT]")
                print(f"[DISRUPTION MANAGEMENT] =========================================")
                print(f"[DISRUPTION MANAGEMENT] NUMPY VERSION COMPATIBILITY ISSUE")
                print(f"[DISRUPTION MANAGEMENT] =========================================")
                print(f"[DISRUPTION MANAGEMENT] The model was trained with a different numpy version.")
                print(f"[DISRUPTION MANAGEMENT]")
                print(f"[DISRUPTION MANAGEMENT] SOLUTIONS:")
                print(f"[DISRUPTION MANAGEMENT] 1. Reinstall dependencies:")
                print(f"[DISRUPTION MANAGEMENT]    poetry install")
                print(f"[DISRUPTION MANAGEMENT]")
                print(f"[DISRUPTION MANAGEMENT] 2. Or upgrade numpy/scikit-learn:")
                print(f"[DISRUPTION MANAGEMENT]    poetry add numpy@latest scikit-learn@latest")
                print(f"[DISRUPTION MANAGEMENT]")
                print(f"[DISRUPTION MANAGEMENT] 3. Or retrain the model with current numpy version")
                print(f"[DISRUPTION MANAGEMENT] =========================================")
            
            self.model = None
    
    async def setup(self):
        """Setup agent behaviors."""
        if self.model is None:
            print(f"[DISRUPTION MANAGEMENT {self.jid}] WARNING: Model not loaded. Agent will not make predictions.")
            return
        
        print(f"[DISRUPTION MANAGEMENT {self.jid}] Agente iniciado com modelo: {self.model_type}")
        
        # Periodic behavior for making predictions
        class PredictionBehaviour(PeriodicBehaviour):
            async def run(self):
                await self.agent.make_predictions()
        
        # Run predictions every 20 seconds
        check_interval = 20
        start_at = datetime.now() + timedelta(seconds=check_interval)
        period = PredictionBehaviour(period=check_interval, start_at=start_at)
        self.add_behaviour(period)
    
    def _collect_features(self, intersection_id=None):
        """
        Collect features from environment for ML model prediction.
        
        Args:
            intersection_id: Optional intersection ID for per-intersection features
        
        Returns:
            List of feature values in the order expected by the model:
            [hour, traffic_density, total_cars, total_stopped, avg_speed, 
             active_disruptions, speed_modifier]
            
        Note: Model was trained with 7 features (congestion_ratio was not included).
        """
        env = self.environment
        
        # System-wide features
        hour = env.simulation_time.hour
        total_cars = len(env.car_positions)
        
        # Calculate total stopped cars (including those stopped behind others)
        total_stopped = env.count_all_stopped_cars()
        
        avg_speed = env.get_average_speed()
        active_disruptions = len(env.active_disruptions)
        speed_modifier = env.speed_modifier
        
        # Use the same traffic_density calculation as training data (from TRAFFIC_PATTERNS)
        # This matches how traffic_density was calculated during model training
        # The model was trained with traffic_density from TRAFFIC_PATTERNS based on hour, not car count
        traffic_density = env.current_traffic_density
        
        # Model was trained with these 7 features (without congestion_ratio):
        # ['hour', 'traffic_density', 'total_cars', 'total_stopped', 'avg_speed', 'active_disruptions', 'speed_modifier']
        features = [
            hour,
            traffic_density,
            total_cars,
            total_stopped,
            avg_speed,
            active_disruptions,
            speed_modifier
        ]
        
        return features
    
    async def make_predictions(self):
        """Make predictions for all intersections and broadcast warnings."""
        if self.model is None:
            return
        
        # Check if debug mode is enabled
        debug_enabled = getattr(self.environment, 'show_prediction_debug', False)
        
        if debug_enabled:
            print(f"\n[DISRUPTION MANAGEMENT {self.jid}] ========== PREDIÇÕES ML ==========")
            print(f"[DISRUPTION MANAGEMENT] Modelo: {self.model_type}")
            print(f"[DISRUPTION MANAGEMENT] Hora: {self.environment.simulation_time.hour:02d}:00")
        
        current_predictions = {}
        
        # Make predictions for each intersection
        for intersection_id in INTERSECTION_IDS:
            # Skip if intersection already has an active disruption
            if intersection_id in self.environment.active_disruptions:
                # Clear prediction if disruption is now active
                if hasattr(self.environment, 'clear_predicted_disruption'):
                    self.environment.clear_predicted_disruption(intersection_id)
                continue
            
            # Collect features
            features = self._collect_features(intersection_id)
            
            if debug_enabled:
                intersection_name = self.environment.get_intersection_name(intersection_id)
                print(f"\n[DISRUPTION MANAGEMENT] --- {intersection_name} ({intersection_id}) ---")
                print(f"[DISRUPTION MANAGEMENT] Features: hour={features[0]}, density={features[1]:.2f}, "
                      f"cars={features[2]}, stopped={features[3]}, speed={features[4]:.1f}, "
                      f"disruptions={features[5]}, modifier={features[6]:.2f}")
            
            try:
                # Validate features (model expects 7 features)
                if len(features) != 7:
                    print(f"[DISRUPTION MANAGEMENT {self.jid}] WARNING: Invalid feature count: {len(features)}. Expected 7.")
                    continue
                
                # Create DataFrame with feature names to match training data format
                # Feature names from training: ['hour', 'traffic_density', 'total_cars', 'total_stopped', 
                #                                'avg_speed', 'active_disruptions', 'speed_modifier']
                feature_names = ['hour', 'traffic_density', 'total_cars', 'total_stopped', 
                                'avg_speed', 'active_disruptions', 'speed_modifier']
                feature_df = pd.DataFrame([features], columns=feature_names)
                
                # Make prediction using DataFrame (suppresses feature name warning)
                # The DataFrame has the correct feature names matching training data
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning)
                    prediction = self.model.predict(feature_df)[0]
                
                # For regression models, prediction is a probability/score
                # For classification models, prediction is 0 or 1
                if self.model_type == "regression":
                    # Convert probability to binary prediction using threshold
                    prediction_value = float(prediction)
                    binary_prediction = 1 if prediction_value >= self.regression_threshold else 0
                    confidence = max(0.0, min(1.0, prediction_value))  # Clamp to [0, 1]
                    
                    if debug_enabled:
                        print(f"[DISRUPTION MANAGEMENT] Regressão: valor={prediction_value:.4f}, "
                              f"threshold={self.regression_threshold}, predição={'SIM' if binary_prediction == 1 else 'NÃO'}")
                else:
                    # Classification: prediction is already binary
                    binary_prediction = int(prediction)
                    # Get prediction probability if model supports it
                    try:
                        with warnings.catch_warnings():
                            warnings.filterwarnings("ignore", category=UserWarning)
                            proba = self.model.predict_proba(feature_df)[0]
                        confidence = float(max(proba))  # Max probability as confidence
                        
                        if debug_enabled:
                            print(f"[DISRUPTION MANAGEMENT] Classificação: predição={'SIM' if binary_prediction == 1 else 'NÃO'}, "
                                  f"probabilidades={proba}, confiança={confidence:.4f}")
                    except AttributeError:
                        # Model doesn't support predict_proba (e.g., some regression models)
                        confidence = 1.0 if binary_prediction == 1 else 0.0
                        
                        if debug_enabled:
                            print(f"[DISRUPTION MANAGEMENT] Classificação: predição={'SIM' if binary_prediction == 1 else 'NÃO'}, "
                                  f"confiança={confidence:.4f} (sem predict_proba)")
                    except Exception as e:
                        print(f"[DISRUPTION MANAGEMENT {self.jid}] Error getting prediction probability: {e}")
                        confidence = 1.0 if binary_prediction == 1 else 0.0
                        
                        if debug_enabled:
                            print(f"[DISRUPTION MANAGEMENT] Classificação: predição={'SIM' if binary_prediction == 1 else 'NÃO'}, "
                                  f"confiança={confidence:.4f} (erro ao obter probabilidade)")
                
                # Store prediction (both positive and negative for UI display)
                prediction_data = {
                    'prediction': binary_prediction,
                    'confidence': confidence,
                    'timestamp': self.environment.simulation_time,
                    'model_type': self.model_type
                }
                
                # Always store prediction in current_predictions for UI display
                current_predictions[intersection_id] = prediction_data
                
                # Update environment for visual display (check if method exists)
                # Store ALL predictions (including negative ones) when debug is enabled
                if hasattr(self.environment, 'set_predicted_disruption'):
                    # If debug is enabled, store all predictions (positive and negative)
                    # Otherwise, only store positive predictions
                    if debug_enabled or binary_prediction == 1:
                        self.environment.set_predicted_disruption(intersection_id, prediction_data)
                    elif binary_prediction == 0:
                        # Clear if not in debug mode and prediction is negative
                        self.environment.clear_predicted_disruption(intersection_id)
                else:
                    print(f"[DISRUPTION MANAGEMENT {self.jid}] WARNING: Environment.set_predicted_disruption not available")
                
                # Only broadcast warnings for positive predictions
                if binary_prediction == 1:
                    # Broadcast warning if this is a new prediction or confidence changed significantly
                    should_broadcast = True
                    if intersection_id in self.last_predictions:
                        last_pred = self.last_predictions[intersection_id]
                        if last_pred.get('prediction', 0) == 1:
                            last_conf = last_pred.get('confidence', 0)
                            # Only broadcast if confidence changed by more than 0.1
                            if abs(confidence - last_conf) < 0.1:
                                should_broadcast = False
                    
                    if should_broadcast:
                        await self._broadcast_warning(intersection_id, prediction_data)
                else:
                    # No disruption predicted
                    if debug_enabled:
                        print(f"[DISRUPTION MANAGEMENT] Resultado: NÃO (sem disruption prevista)")
            
            except Exception as e:
                print(f"[DISRUPTION MANAGEMENT {self.jid}] Error making prediction for {intersection_id}: {e}")
                continue
        
        # Update last predictions
        self.last_predictions = current_predictions
        
        # Clear predictions that are no longer predicted
        # When debug is enabled, we keep all predictions (including negative ones)
        # When debug is disabled, only clear negative predictions that are no longer in current_predictions
        for intersection_id in list(self.last_predictions.keys()):
            if intersection_id not in current_predictions:
                # Only clear if not in debug mode (in debug mode, we want to show all predictions)
                if not debug_enabled:
                    if hasattr(self.environment, 'clear_predicted_disruption'):
                        self.environment.clear_predicted_disruption(intersection_id)
                    self.last_predictions.pop(intersection_id, None)
        
        if debug_enabled:
            # Count positive and negative predictions
            positive_predictions = {k: v for k, v in current_predictions.items() if v.get('prediction', 0) == 1}
            negative_predictions = {k: v for k, v in current_predictions.items() if v.get('prediction', 0) == 0}
            
            print(f"\n[DISRUPTION MANAGEMENT] ========== RESUMO DAS PREDIÇÕES ==========")
            print(f"[DISRUPTION MANAGEMENT] Total de interseções analisadas: {len(INTERSECTION_IDS)}")
            print(f"[DISRUPTION MANAGEMENT] Previsões positivas (disruption prevista): {len(positive_predictions)}")
            print(f"[DISRUPTION MANAGEMENT] Previsões negativas (sem disruption): {len(negative_predictions)}")
            
            if positive_predictions:
                print(f"\n[DISRUPTION MANAGEMENT] Interseções com disruption prevista:")
                for intersection_id, pred_data in positive_predictions.items():
                    intersection_name = self.environment.get_intersection_name(intersection_id)
                    conf_pct = pred_data['confidence'] * 100
                    print(f"[DISRUPTION MANAGEMENT]   - {intersection_name}: {conf_pct:.1f}% confiança")
            else:
                print(f"\n[DISRUPTION MANAGEMENT] Nenhuma disruption prevista no momento.")
            print(f"[DISRUPTION MANAGEMENT] ==========================================\n")
    
    async def _broadcast_warning(self, intersection_id, prediction_data):
        """Broadcast disruption warning to all agents via FIPA Inform Protocol."""
        conv_id = str(uuid.uuid4())
        
        # Create warning message
        warning_message = {
            "type": "DISRUPTION_WARNING",
            "intersection_id": intersection_id,
            "prediction": prediction_data['prediction'],
            "confidence": prediction_data['confidence'],
            "timestamp": prediction_data['timestamp'].isoformat(),
            "model_type": prediction_data['model_type']
        }
        
        message_body = json.dumps(warning_message)
        
        # Broadcast to traffic light agents
        for tl_jid in self.traffic_light_jids:
            msg = Message(to=tl_jid)
            msg.set_metadata("performative", "inform")
            msg.set_metadata("protocol", "fipa-inform")
            msg.set_metadata("conversation-id", conv_id)
            msg.set_metadata("message_type", "disruption_warning")
            msg.body = message_body
            await self.send(msg)
        
        # Broadcast to MapUpdaterAgent
        msg = Message(to="central@localhost")
        msg.set_metadata("performative", "inform")
        msg.set_metadata("protocol", "fipa-inform")
        msg.set_metadata("conversation-id", conv_id)
        msg.set_metadata("message_type", "disruption_warning")
        msg.body = message_body
        await self.send(msg)
        
        # Broadcast to all car agents (using a pattern - cars register with pattern "carro_*@localhost")
        # Note: SPADE doesn't support wildcard messaging directly, so we track car JIDs
        # For now, we'll rely on cars subscribing to receive these messages
        # Or we could maintain a list of car JIDs from the environment
        
        intersection_name = self.environment.get_intersection_name(intersection_id)
        confidence_pct = prediction_data['confidence'] * 100
        print(f"[DISRUPTION MANAGEMENT {self.jid}] WARNING: Disruption predicted at {intersection_name} "
              f"(confidence: {confidence_pct:.1f}%)")

