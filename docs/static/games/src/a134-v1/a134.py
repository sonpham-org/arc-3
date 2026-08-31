"""a134 Tie Break -- configure a shared geometric priority for equal routes."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,GATE,ROUTE,CUE,AGENT,CHOICE_A,CHOICE_B,CONSENSUS,SPLIT,CURSOR=0,8,9,13,12,10,14,4,6,11
BAD=15
LEVELS=[
 {"name":"Move Cue","seq":(1,)},{"name":"Rotate Cue","seq":(2,)},
 {"name":"Select Route","seq":(3,1)},{"name":"Resolve Tie","seq":(1,2,3,4,2)},
 {"name":"Shared Priority","seq":(1,3,2,1,4,3,2)},{"name":"Tie Break","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 cue,orientation,focus,choices,consensus,history,snapshot=s
 if a==1:cue=(cue+1)%5;history=(history+(1,))[-8:]
 elif a==2:orientation=(orientation+1)%4;history=(history+(2,))[-8:]
 elif a==3:focus=(focus+1)%3;history=(history+(3,))[-8:]
 elif a==4:
  choices=tuple((cue+orientation+i%2+focus)%3 for i in range(5));consensus=max(choices.count(k) for k in range(3));history=(history+(4,))[-8:]
 elif a==5:snapshot=(cue,orientation,focus,choices,consensus,history)
 return cue,orientation,focus,choices,consensus,history,snapshot
for q in LEVELS:
 s=(0,0,0,(),0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GATE
  for i in range(3):y=15+i*14;f[y:y+7,8:52]=ROUTE;f[y-2:y+9,52:58]=CHOICE_A if i==g.focus else CHOICE_B
  for i in range(5):f[10+i*9:16+i*9,6:12]=AGENT
  cx=18+g.cue*7;cy=10+g.orientation*11;f[cy:cy+8,cx:cx+8]=CUE
  for i,c in enumerate(g.choices):f[54:58,8+i*9:15+i*9]=CHOICE_A if c==g.focus else CHOICE_B
  f[7:10,8:8+g.consensus*8]=CONSENSUS if g.consensus==5 else SPLIT
  if g.bad:f[1:4,18:46]=BAD
  return f
class A134(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a134",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.cue,self.orientation,self.focus,self.choices,self.consensus,self.history,self.snapshot=(0,0,0,(),0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.cue,self.orientation,self.focus,self.choices,self.consensus,self.history,self.snapshot=advance((self.cue,self.orientation,self.focus,self.choices,self.consensus,self.history,self.snapshot),a)
  elif a==6:
   if (self.cue,self.orientation,self.focus,self.choices,self.consensus,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
