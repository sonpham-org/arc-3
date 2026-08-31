"""a111 Occlusion Cover -- screen fragile cells while preserving phased solar sightlines."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FIELD,FRAGILE,SOLAR,SCREEN,EMITTER,RAY,HIDDEN,VISIBLE,BAD=7,8,6,10,12,14,11,4,13,15
LEVELS=[
 {"name":"Place Screen","seq":(1,)},{"name":"Rotate Emitter","seq":(2,)},
 {"name":"Select Screen","seq":(3,1)},{"name":"Protect One Phase","seq":(1,2,4,3,1)},
 {"name":"Preserve Receiver","seq":(2,1,3,2,1,4,3)},{"name":"Occlusion Cover","seq":(1,3,2,1,4,2,3,1,4,2)},
]
def advance(s,a):
 screens,cursor,phase,hidden,visible,violations,history,snapshot=s;sc=list(screens)
 if a==1:sc[cursor]=(sc[cursor]+1)%9;history=(history+(1,))[-8:]
 elif a==2:phase=(phase+1)%4;history=(history+(2,))[-8:]
 elif a==3:cursor=(cursor+1)%3;history=(history+(3,))[-8:]
 elif a==4:
  fragile=(2,5,8);solar=(0,4,7);hidden=sum(1<<i for i,c in enumerate(fragile) if any((p+phase)%9 in (c,(c-1)%9) for p in sc));visible=sum(1<<i for i,c in enumerate(solar) if all((p+phase)%9!=c for p in sc));violations=(3-hidden.bit_count())+(3-visible.bit_count());history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(sc),cursor,phase,hidden,visible,violations,history)
 return tuple(sc),cursor,phase,hidden,visible,violations,history,snapshot
for x in LEVELS:
 s=((1,3,6),0,0,0,0,6,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD
  for i in range(9):
   x=10+(i%3)*16;y=12+(i//3)*15;f[y:y+11,x:x+11]=FRAGILE if i in (2,5,8) else SOLAR if i in (0,4,7) else RAY
  for i,p in enumerate(g.screens):
   x=8+(p%3)*16;y=10+(p//3)*15;f[y:y+15,x:x+3]=SCREEN;f[y-3:y,x:x+8]=VISIBLE if i==g.cursor else HIDDEN
  ex,ey=((30,6),(57,30),(30,56),(5,30))[g.phase];f[max(0,ey-3):min(64,ey+4),max(0,ex-3):min(64,ex+4)]=EMITTER
  f[55:59,8:8+g.violations*7]=BAD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A111(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a111",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.screens,self.cursor,self.phase,self.hidden,self.visible,self.violations,self.history,self.snapshot=((1,3,6),0,0,0,0,6,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.screens,self.cursor,self.phase,self.hidden,self.visible,self.violations,self.history,self.snapshot=advance((self.screens,self.cursor,self.phase,self.hidden,self.visible,self.violations,self.history,self.snapshot),a)
  elif a==6:
   if (self.screens,self.cursor,self.phase,self.hidden,self.visible,self.violations,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
