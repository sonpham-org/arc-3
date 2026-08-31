"""a068 Beat Detector -- infer the coincidence period of two nearby rotors."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CHAMBER,ROTOR_A,ROTOR_B,MARKER,BEAT,TIMELINE,TRANSFER,WINDOW,BAD=12,8,9,14,10,13,4,11,6,15
LEVELS=[
 {"name":"Advance Rotors","seq":(1,)},{"name":"Observe Coincidence","seq":(1,1)},
 {"name":"Change Step","seq":(2,1,1)},{"name":"Predict Beat","seq":(1,2,1,3,1)},
 {"name":"Schedule Transfer","seq":(1,1,2,1,3,4,1)},{"name":"Beat Detector","seq":(2,1,1,3,1,2,1,4,1,1)},
]
def advance(s,a):
 phases,freqs,time,step,coincidences,prediction,transfer,history,snapshot=s;p=list(phases)
 if a==1:
  time+=step;p=[(p[i]+freqs[i]*step)%12 for i in range(2)]
  if p[0]==p[1]:coincidences=(coincidences+(time,))[-5:]
  history=(history+(1,))[-8:]
 elif a==2:step=1+step%3;history=(history+(2,))[-8:]
 elif a==3:prediction=(prediction+1+len(coincidences))%12;history=(history+(3,))[-8:]
 elif a==4:transfer=(time,p[0],p[1],prediction);history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(p),freqs,time,step,coincidences,prediction,transfer,history)
 return tuple(p),freqs,time,step,coincidences,prediction,transfer,history,snapshot
for x in LEVELS:
 s=((0,0),(5,4),0,1,(),0,None,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CHAMBER
  for i,(col,p) in enumerate(zip((ROTOR_A,ROTOR_B),g.phases)):
   cx=20+i*25;f[14:40,cx-10:cx+10]=col;f[18:36,cx-7:cx+7]=CHAMBER;x=cx-6+(p%4)*4;y=20+(p//4)*5;f[y:y+5,x:x+5]=MARKER
  f[45:50,8:56]=TIMELINE
  for i,t in enumerate(g.coincidences):x=9+(t%12)*4;f[43:52,x:x+3]=BEAT
  f[53:57,8:8+g.prediction*4]=WINDOW
  if g.transfer:f[8:12,25:39]=TRANSFER
  if g.bad:f[1:4,18:46]=BAD
  return f
class A068(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a068",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.phases,self.freqs,self.time,self.sample_step,self.coincidences,self.prediction,self.transfer,self.history,self.snapshot=((0,0),(5,4),0,1,(),0,None,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.phases,self.freqs,self.time,self.sample_step,self.coincidences,self.prediction,self.transfer,self.history,self.snapshot=advance((self.phases,self.freqs,self.time,self.sample_step,self.coincidences,self.prediction,self.transfer,self.history,self.snapshot),a)
  elif a==6:
   if (self.phases,self.freqs,self.time,self.sample_step,self.coincidences,self.prediction,self.transfer,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
