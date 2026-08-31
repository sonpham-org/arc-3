"""a012 Maintenance Window -- schedule mutually exclusive service before wear deadlines."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FACTORY,MACHINE,ROTOR,WEAR,SERVICE,WINDOW,GOAL,BAD=1,10,14,8,12,6,11,13,15
LEVELS=[{"name":"Visible Wear","seq":(1,)},{"name":"First Window","seq":(2,1)},{"name":"Preventive Service","seq":(3,1,2)},{"name":"Phase Advance","seq":(4,2,1,3)},{"name":"Deadline Order","seq":(2,3,1,4,2,1)},{"name":"Maintenance Window","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 wear,phase,selected,serviced,history,run=s;w=list(wear);sv=list(serviced)
 if a==1:selected=(selected+1)%3
 elif a==2:phase=(phase+1)%6;w=[min(6,v+1+(i==phase%3)) for i,v in enumerate(w)]
 elif a==3:
  if selected==phase%3:w[selected]=max(0,w[selected]-3);sv[selected]+=1
  history=history+((tuple(w),phase,selected,tuple(sv)),)
 elif a==4:phase=(phase+2)%6;w=[min(6,v+1) for v in w]
 elif a==5:run=(tuple(w),phase,selected,tuple(sv),history[-4:])
 return tuple(w),phase,selected,tuple(sv),history,run
for x in LEVELS:
 s=((1,3,5),0,0,(0,0,0),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FACTORY
  for i,v in enumerate(g.wear):x=8+i*18;f[8:31,x:x+13]=MACHINE;f[11:18,x+3:x+10]=ROTOR;f[28-v*3:29,x+2:x+11]=WEAR;f[20:24,x+2:x+11]=WINDOW if i==g.phase%3 else SERVICE
  for i,v in enumerate(g.serviced):x=9+i*17;f[37:42,x:x+12]=SERVICE;f[43:46,x:x+2+v*3]=ROTOR
  f[52:56,8:8+g.phase*8+7]=WINDOW
  if g.run:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A012(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a012",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.wear=(1,3,5);self.phase=self.selected=0;self.serviced=(0,0,0);self.history=();self.run=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.wear,self.phase,self.selected,self.serviced,self.history,self.run=advance((self.wear,self.phase,self.selected,self.serviced,self.history,self.run),a)
  elif a==6:
   if (self.wear,self.phase,self.selected,self.serviced,self.history,self.run)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
