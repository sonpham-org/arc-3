"""q622 Tide Sandbox -- reset tidal trials while observed current evidence persists."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,BASIN,SHELL,CURRENT,EVIDENCE,RESET,GOAL,BAD=4,9,11,14,10,6,12,13,15
LEVELS=[
 {"name":"First Trial","seq":(1,3)},{"name":"Reversing Current","seq":(2,3,4)},
 {"name":"Persistent Wake","seq":(1,3,4,2,3)},{"name":"Safe Contrast","seq":(2,1,3,4,1,3)},
 {"name":"Irreversible Gate","seq":(1,2,3,4,2,2,3)},
 {"name":"Tide Sandbox","seq":(2,1,3,4,1,2,3,4,2,3)}]
def advance(s,a):
 shells,current,phase,evidence,trials,commit=s;v=list(shells)
 if a==1:v[0],v[1]=v[1],v[0];phase=(phase+1)%4
 elif a==2:v=v[1:]+v[:1];current^=1;phase=(phase+2+current)%4
 elif a==3:evidence=evidence+((tuple(v),current,phase),);trials+=1
 elif a==4:v[:]=[0,1,2];current=phase=0
 elif a==5:commit=(tuple(v),current,phase,evidence[-3:],trials)
 return tuple(v),current,phase,evidence,trials,commit
for x in LEVELS:
 s=((0,1,2),0,0,(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAB;f[8:31,7:29]=BASIN;f[8:31,35:57]=RESET
  for i,shell in enumerate(g.shells):x=9+i*7;f[24-shell*4:29,x:x+6]=SHELL
  for i,e in enumerate(g.evidence[-5:]):x=8+i*10;f[36:42,x:x+7]=EVIDENCE;f[43:46,x:x+2+e[2]]=CURRENT
  f[50:54,8:8+g.current*25+12]=CURRENT;f[55:59,8:8+g.phase*11+7]=BASIN
  if g.commit:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q622(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q622",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.shells=(0,1,2);self.current=self.phase=self.trials=0;self.evidence=();self.commit=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.shells,self.current,self.phase,self.evidence,self.trials,self.commit=advance((self.shells,self.current,self.phase,self.evidence,self.trials,self.commit),a)
  elif a==6:
   if (self.shells,self.current,self.phase,self.evidence,self.trials,self.commit)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
