"""a098 Boundary Echo -- diagnose phase-inverting walls from returned pulses."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,VAULT,PATH,WALL,PROBE,ECHO,INVERT,BRANCH,REINFORCE,BAD=10,8,9,4,12,14,11,13,6,15
LEVELS=[
 {"name":"Probe Wall","seq":(1,)},{"name":"Select Boundary","seq":(2,)},
 {"name":"Read Echo","seq":(1,2,1)},{"name":"Schedule Phase","seq":(1,3,2,1,4)},
 {"name":"Cancel Branch","seq":(1,2,1,3,4,2,4)},{"name":"Boundary Echo","seq":(1,2,1,3,4,2,1,4,3,4)},
]
def advance(s,a):
 materials,cursor,echoes,phase,branches,diagnosis,history,snapshot=s
 if a==1:echo=(cursor,materials[cursor]^phase);echoes=(echoes+(echo,))[-6:];diagnosis|=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%3;history=(history+(2,))[-8:]
 elif a==3:phase^=1;history=(history+(3,))[-8:]
 elif a==4:branches=((branches[0]+1+phase)%5,(branches[1]+1+(phase^materials[cursor]))%5);history=(history+(4,))[-8:]
 elif a==5:snapshot=(materials,cursor,echoes,phase,branches,diagnosis,history)
 return materials,cursor,echoes,phase,branches,diagnosis,history,snapshot
for x in LEVELS:
 s=((0,1,1),0,(),0,(0,0),0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=VAULT;f[27:35,7:48]=PATH
  for i,m in enumerate(g.materials):x=15+i*16;f[12:50,x:x+5]=INVERT if (g.diagnosis&(1<<i) and m) else WALL
  f[24:38,7:13]=PROBE
  for i,(wall,phase) in enumerate(g.echoes):f[51:55,8+i*8:14+i*8]=INVERT if phase else ECHO
  for i,v in enumerate(g.branches):f[18+i*22:27+i*22,49:58]=BRANCH;f[20+i*22:25+i*22,50:50+v]=REINFORCE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A098(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a098",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.materials,self.cursor,self.echoes,self.phase,self.branches,self.diagnosis,self.history,self.snapshot=((0,1,1),0,(),0,(0,0),0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.materials,self.cursor,self.echoes,self.phase,self.branches,self.diagnosis,self.history,self.snapshot=advance((self.materials,self.cursor,self.echoes,self.phase,self.branches,self.diagnosis,self.history,self.snapshot),a)
  elif a==6:
   if (self.materials,self.cursor,self.echoes,self.phase,self.branches,self.diagnosis,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
