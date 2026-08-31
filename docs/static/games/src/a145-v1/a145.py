"""a145 Self or Wind -- separate commanded displacement from periodic exogenous motion."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FIELD,OBJECT,COMMAND,WIND,SELF_CAUSE,EXOGENOUS,NULL,TRACE,BAD=12,8,10,14,13,4,6,11,9,15
WIND_SEQ=(1,0,-1,0)
LEVELS=[
 {"name":"Command Motion","seq":(1,)},{"name":"Reverse Command","seq":(2,)},
 {"name":"Null Action","seq":(3,1)},{"name":"Compare Motion","seq":(1,2,3,4,2)},
 {"name":"Separate Causes","seq":(1,3,2,1,4,3,2)},{"name":"Self or Wind","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 x,command,wind_phase,last_delta,self_part,wind_part,history,snapshot=s
 if a in (1,2,3):
  command=1 if a==1 else -1 if a==2 else 0;wind_part=WIND_SEQ[wind_phase];self_part=command;last_delta=command+wind_part;x=(x+last_delta)%9;wind_phase=(wind_phase+1)%4;history=(history+(a,))[-8:]
 elif a==4:history=(history+(4,))[-8:]
 elif a==5:snapshot=(x,command,wind_phase,last_delta,self_part,wind_part,history)
 return x,command,wind_phase,last_delta,self_part,wind_part,history,snapshot
for q in LEVELS:
 s=(4,0,0,0,0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD;f[28:37,8:56]=TRACE;px=9+g.x*5;f[24:41,px:px+8]=OBJECT
  f[10:15,8:28]=COMMAND if g.command else NULL;f[10:15,31:55]=WIND;f[50:54,8:8+(g.self_part+1)*10]=SELF_CAUSE;f[55:59,8:8+(g.wind_part+1)*10]=EXOGENOUS
  if g.bad:f[1:4,18:46]=BAD
  return f
class A145(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a145",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.x,self.command,self.wind_phase,self.last_delta,self.self_part,self.wind_part,self.history,self.snapshot=(4,0,0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.x,self.command,self.wind_phase,self.last_delta,self.self_part,self.wind_part,self.history,self.snapshot=advance((self.x,self.command,self.wind_phase,self.last_delta,self.self_part,self.wind_part,self.history,self.snapshot),a)
  elif a==6:
   if (self.x,self.command,self.wind_phase,self.last_delta,self.self_part,self.wind_part,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
